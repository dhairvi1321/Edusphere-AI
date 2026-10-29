from datetime import date, timedelta
import os
from uuid import uuid4
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from mongoengine.connection import get_db
from pymongo.errors import ServerSelectionTimeoutError

from .models import StudyPlan, Subject, SyllabusTopic
from .views import (
    GenerateStudyPlan,
    StudyInsights,
    StudyPlanListCreate,
    StudyPlanDetail,
    TopicDetail,
    _build_session_pool,
    _priority_score,
    _schedule_sessions,
    _topic_duration,
    _topic_priority_key,
)


class StudyPlannerSchedulingTests(SimpleTestCase):
    def setUp(self):
        self.start = date(2026, 10, 29)
        self.end = date(2026, 10, 31)

    @staticmethod
    def topic(topic_id, difficulty=1):
        return {
            'subject': 'Math',
            'subject_id': 'subject-1',
            'topic': f'Topic {topic_id}',
            'topic_id': topic_id,
            '_difficulty_key': difficulty,
        }

    def test_sessions_obey_daily_budget_and_dates(self):
        pool = [self.topic('hard', 0), self.topic('medium', 1), self.topic('easy', 2)]
        sessions = _schedule_sessions(pool, self.start, self.end, 1)

        self.assertEqual(len({s['topic_id'] for s in sessions}), len(sessions))
        self.assertTrue(all(self.start.isoformat() <= s['date'] <= self.end.isoformat() for s in sessions))
        self.assertTrue(all(s['duration_minutes'] <= 60 for s in sessions))
        for session_date in {s['date'] for s in sessions}:
            day_total = sum(s['duration_minutes'] for s in sessions if s['date'] == session_date)
            self.assertLessEqual(day_total, 60)

    def test_duplicate_topic_ids_are_only_scheduled_once(self):
        topic = self.topic('same')
        sessions = _schedule_sessions([topic, dict(topic)], self.start, self.end, 2)
        self.assertEqual([s['topic_id'] for s in sessions], ['same'])

    def test_insufficient_time_leaves_topics_unscheduled_without_overbooking(self):
        pool = [self.topic(str(index), 2) for index in range(8)]
        sessions = _schedule_sessions(pool, self.start, self.start, 1)

        self.assertEqual(len(sessions), 3)
        self.assertLess(len(sessions), len(pool))
        self.assertLessEqual(sum(s['duration_minutes'] for s in sessions), 60)

    def test_invalid_capacity_and_date_range_return_empty(self):
        pool = [self.topic('one')]
        self.assertEqual(_schedule_sessions([], self.start, self.end, 1), [])
        self.assertEqual(_schedule_sessions(pool, self.start, self.end, 0), [])
        self.assertEqual(_schedule_sessions(pool, self.end, self.start, 1), [])
        self.assertEqual(_schedule_sessions(pool, self.start, self.end, True), [])

    def test_unknown_difficulty_uses_safe_medium_duration(self):
        self.assertEqual(_topic_duration({'_difficulty_key': 99}), 30)

    @patch('academics.views.Assignment.objects')
    @patch('academics.views.Exam.objects')
    @patch('academics.views.Subject.objects')
    def test_missing_or_invalid_deadlines_and_difficulty_use_safe_defaults(
        self, subjects, exams, assignments
    ):
        completed = SimpleNamespace(
            id='completed', title='Done', is_completed=True, difficulty='hard'
        )
        pending = SimpleNamespace(
            id='pending', title='Pending', is_completed=False, difficulty='unexpected'
        )
        subject = SimpleNamespace(id='subject-1', name='Math', topics=[completed, pending])
        subjects.return_value = [subject]
        exams.return_value = [SimpleNamespace(subject_id='subject-1', exam_date='invalid-date')]
        assignments.return_value = [SimpleNamespace(
            subject_id='subject-1', is_completed=False, due_date='invalid-date', priority='unexpected'
        )]

        pool = _build_session_pool('student-1')

        self.assertEqual([item['topic_id'] for item in pool], ['pending'])
        self.assertEqual(pool[0]['_difficulty_key'], 1)
        self.assertIsNone(pool[0]['deadline_days'])
        self.assertAlmostEqual(pool[0]['_priority_score'], 0.4166667)

    @patch('academics.views.Assignment.objects')
    @patch('academics.views.Exam.objects')
    @patch('academics.views.Subject.objects')
    def test_nearest_relevant_deadline_drives_urgency(self, subjects, exams, assignments):
        topic = SimpleNamespace(
            id='topic-1', title='Soon', is_completed=False, difficulty='medium',
            status='not_started', revision_required=False,
        )
        subject = SimpleNamespace(id='subject-1', name='Math', topics=[topic])
        subjects.return_value = [subject]
        exams.return_value = [SimpleNamespace(
            subject_id='subject-1', exam_date=(date.today() + timedelta(days=1)).isoformat()
        )]
        assignments.return_value = [SimpleNamespace(
            subject_id='subject-1', is_completed=False,
            due_date=(date.today() + timedelta(days=5)).isoformat(),
        )]

        pool = _build_session_pool('student-1')

        self.assertEqual(pool[0]['deadline_days'], 1)
        self.assertAlmostEqual(pool[0]['_priority_score'], 0.6166667)

    def test_documented_worked_example_scores_and_order(self):
        topic_a = _priority_score(5, 1.0, 'not_started', False)
        topic_b = _priority_score(2, 2 / 3, 'in_progress', True)
        topic_c = _priority_score(10, 1 / 3, 'not_started', False)

        self.assertAlmostEqual(topic_a, 0.567, places=3)
        self.assertAlmostEqual(topic_b, 0.525, places=3)
        self.assertAlmostEqual(topic_c, 0.370, places=3)
        items = [
            {'topic': 'Topic C', 'subject': 'Math', 'topic_id': 'c', '_priority_score': topic_c},
            {'topic': 'Topic B', 'subject': 'Math', 'topic_id': 'b', '_priority_score': topic_b},
            {'topic': 'Topic A', 'subject': 'Math', 'topic_id': 'a', '_priority_score': topic_a},
        ]
        self.assertEqual([item['topic'] for item in sorted(items, key=_topic_priority_key)], [
            'Topic A', 'Topic B', 'Topic C'
        ])

    def test_revision_flag_increases_score_and_equal_scores_break_by_name(self):
        base_score = _priority_score(4, 2 / 3, 'in_progress', False)
        revision_score = _priority_score(4, 2 / 3, 'in_progress', True)
        self.assertAlmostEqual(revision_score - base_score, 0.10)

        common = {'_priority_score': 0.5, 'subject': 'Math', 'topic_id': 'same'}
        items = [
            {**common, 'topic': 'Zeta'},
            {**common, 'topic': 'Alpha'},
        ]
        self.assertEqual([item['topic'] for item in sorted(items, key=_topic_priority_key)], ['Alpha', 'Zeta'])

    def test_missing_deadline_has_zero_urgency_and_overdue_deadline_is_clamped(self):
        no_deadline = _priority_score(None, 2 / 3, 'not_started', False)
        invalid_deadline = _priority_score('invalid', 2 / 3, 'not_started', False)
        overdue = _priority_score(-10, 2 / 3, 'not_started', False)

        self.assertAlmostEqual(no_deadline, invalid_deadline)
        self.assertGreater(overdue, no_deadline)


class StudySessionCompletionTests(SimpleTestCase):
    def setUp(self):
        self.topic = SimpleNamespace(id='topic-1', is_completed=False)
        self.other_topic = SimpleNamespace(id='topic-2', is_completed=False)
        self.subject = SimpleNamespace(topics=[self.topic, self.other_topic], save=MagicMock())
        self.plan = SimpleNamespace(
            id='plan-1',
            title='Study',
            start_date='2026-10-29',
            end_date='2026-10-29',
            daily_hours='2',
            created_at=date(2026, 10, 29),
            sessions=[{
                'session_id': 'session-1',
                'subject_id': 'subject-1',
                'topic_id': 'topic-1',
                'is_completed': False,
            }],
            save=MagicMock(),
        )
        self.request = SimpleNamespace(
            user=SimpleNamespace(id='student-1'),
            data={'session_id': 'session-1', 'is_completed': True},
        )

    @patch('academics.views.Subject.objects')
    def test_completing_session_persists_topic_and_session_for_owner(self, subjects):
        subjects.return_value.first.return_value = self.subject
        with patch.object(StudyPlanDetail, '_get', return_value=self.plan):
            response = StudyPlanDetail().patch(self.request, 'plan-1')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.topic.is_completed)
        self.assertFalse(self.other_topic.is_completed)
        self.assertTrue(self.plan.sessions[0]['is_completed'])
        self.subject.save.assert_called_once_with()
        self.plan.save.assert_called_once_with()
        subjects.assert_called_once_with(user_id='student-1', id='subject-1')

    @patch('academics.views.Subject.objects')
    def test_repeating_completion_is_idempotent(self, subjects):
        subjects.return_value.first.return_value = self.subject
        with patch.object(StudyPlanDetail, '_get', return_value=self.plan):
            first = StudyPlanDetail().patch(self.request, 'plan-1')
            second = StudyPlanDetail().patch(self.request, 'plan-1')

        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertTrue(self.topic.is_completed)
        self.assertTrue(self.plan.sessions[0]['is_completed'])

    def test_non_boolean_completion_is_rejected(self):
        self.request.data['is_completed'] = 'false'
        with patch.object(StudyPlanDetail, '_get', return_value=self.plan):
            response = StudyPlanDetail().patch(self.request, 'plan-1')

        self.assertEqual(response.status_code, 400)
        self.plan.save.assert_not_called()


class TopicRevisionStatusTests(SimpleTestCase):
    def test_topic_edit_persists_status_and_revision_flag(self):
        topic = SimpleNamespace(
            id='topic-1', title='Topic', difficulty='medium', is_completed=False,
            status='not_started', revision_required=False,
        )
        subject = SimpleNamespace(id='subject-1', save=MagicMock())
        request = SimpleNamespace(
            user=SimpleNamespace(id='student-1'),
            data={'status': 'in_progress', 'revision_required': True},
        )
        with patch.object(TopicDetail, '_find', return_value=(subject, topic)):
            response = TopicDetail().patch(request, 'topic-1')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(topic.status, 'in_progress')
        self.assertFalse(topic.is_completed)
        self.assertTrue(topic.revision_required)
        subject.save.assert_called_once_with()


class StudyPlanSaveTests(SimpleTestCase):
    def test_duplicate_session_ids_are_rejected(self):
        request = SimpleNamespace(
            user=SimpleNamespace(id='student-1'),
            data={
                'title': 'Study',
                'start_date': '2026-10-29',
                'end_date': '2026-10-29',
                'sessions': [
                    {'session_id': 'duplicate'},
                    {'session_id': 'duplicate'},
                ],
            },
        )

        response = StudyPlanListCreate().post(request)

        self.assertEqual(response.status_code, 400)

    @patch('academics.views.StudyPlan.objects')
    def test_retrying_same_preview_returns_existing_plan(self, plans):
        existing = SimpleNamespace(
            id='plan-1',
            title='Study',
            start_date='2026-10-29',
            end_date='2026-10-29',
            daily_hours='2',
            created_at=date(2026, 10, 29),
            sessions=[{'session_id': 'session-1', 'topic_id': 'topic-1'}],
        )
        plans.return_value = [existing]
        request = SimpleNamespace(
            user=SimpleNamespace(id='student-1'),
            data={
                'title': 'Study',
                'start_date': '2026-10-29',
                'end_date': '2026-10-29',
                'daily_hours': '2',
                'sessions': [{'session_id': 'session-1', 'topic_id': 'topic-1'}],
            },
        )

        response = StudyPlanListCreate().post(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], 'plan-1')
        plans.assert_called_once_with(
            user_id='student-1',
            title='Study',
            start_date='2026-10-29',
            end_date='2026-10-29',
            daily_hours='2',
        )


class StudyPlannerDatabaseFailureTests(SimpleTestCase):
    def setUp(self):
        self.request = SimpleNamespace(
            user=SimpleNamespace(id='student-1'),
            data={'start_date': '2026-10-29', 'end_date': '2026-10-29', 'daily_hours': 2},
        )

    @patch('academics.views.StudyPlan.objects')
    def test_plan_list_returns_503_when_mongo_is_unavailable(self, plans):
        plans.side_effect = ServerSelectionTimeoutError('test database unavailable')

        response = StudyPlanListCreate().get(self.request)

        self.assertEqual(response.status_code, 503)
        self.assertIn('temporarily unavailable', response.data['detail'])

    @patch('academics.views.Subject.objects')
    def test_generation_returns_503_when_mongo_is_unavailable(self, subjects):
        subjects.side_effect = ServerSelectionTimeoutError('test database unavailable')

        response = GenerateStudyPlan().post(self.request)

        self.assertEqual(response.status_code, 503)

    @patch('academics.views.StudyPlan.objects')
    def test_detail_does_not_misreport_database_failure_as_not_found(self, plans):
        plans.get.side_effect = ServerSelectionTimeoutError('test database unavailable')

        response = StudyPlanDetail().get(self.request, 'plan-id')

        self.assertEqual(response.status_code, 503)


@unittest.skipUnless(
    os.environ.get('STUDY_PLANNER_LIVE_MONGO') == '1',
    'Set STUDY_PLANNER_LIVE_MONGO=1 and DB_NAME to a disposable test database to run MongoDB integration checks.',
)
class LiveMongoStudyPlannerTests(SimpleTestCase):
    """Opt-in integration tests against an explicitly named disposable MongoDB database."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db = get_db()
        cls.db_name = cls.db.name
        if not cls.db_name.startswith('edusphere_studyplanner_test_'):
            raise RuntimeError('Refusing MongoDB integration tests outside the isolated study planner test database.')
        cls.db.client.admin.command('ping')
        cls.db.client.drop_database(cls.db_name)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.db.client.drop_database(cls.db_name)
        finally:
            super().tearDownClass()

    def setUp(self):
        self.user_id = f'student-{uuid4()}'
        self.other_user_id = f'student-{uuid4()}'
        self.subject = Subject(
            user_id=self.user_id,
            name='Planner Integration Subject',
            topics=[SyllabusTopic(
                id='topic-1', title='Persisted topic', difficulty='medium',
                status='in_progress', revision_required=True,
            )],
        ).save()

    @staticmethod
    def request(user_id, data=None):
        return SimpleNamespace(user=SimpleNamespace(id=user_id), data=data or {})

    def test_generated_preview_saves_reloads_and_is_owner_scoped(self):
        preview_response = GenerateStudyPlan().post(self.request(self.user_id, {
            'start_date': '2026-10-29',
            'end_date': '2026-10-29',
            'daily_hours': 2,
            'subject_ids': [str(self.subject.id)],
        }))
        self.assertEqual(preview_response.status_code, 200)
        sessions = preview_response.data['sessions']
        self.assertEqual(len(sessions), 1)
        self.assertAlmostEqual(sessions[0]['priority_score'], 0.392, places=3)

        plan_data = {
            'title': 'Persisted Plan',
            'start_date': '2026-10-29',
            'end_date': '2026-10-29',
            'daily_hours': '2',
            'sessions': sessions,
        }
        create_response = StudyPlanListCreate().post(self.request(self.user_id, plan_data))
        self.assertEqual(create_response.status_code, 201)

        # A fresh API request, as after a page refresh or new login, reads the saved record.
        reloaded = StudyPlanListCreate().get(self.request(self.user_id))
        self.assertEqual(len(reloaded.data), 1)
        self.assertEqual(reloaded.data[0]['id'], create_response.data['id'])
        self.assertEqual(reloaded.data[0]['sessions'][0]['topic_id'], 'topic-1')
        persisted_topic = Subject.objects.get(id=self.subject.id, user_id=self.user_id).topics[0]
        self.assertEqual(persisted_topic.status, 'in_progress')
        self.assertTrue(persisted_topic.revision_required)

        retry_response = StudyPlanListCreate().post(self.request(self.user_id, plan_data))
        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(StudyPlan.objects(user_id=self.user_id).count(), 1)
        self.assertEqual(StudyPlanListCreate().get(self.request(self.other_user_id)).data, [])

    def test_session_completion_updates_database_and_insights_once(self):
        plan = StudyPlan(
            user_id=self.user_id,
            title='Completion Plan',
            start_date=date.today().isoformat(),
            end_date=date.today().isoformat(),
            daily_hours='2',
            sessions=[{
                'session_id': 'session-1',
                'subject': self.subject.name,
                'subject_id': str(self.subject.id),
                'topic_id': 'topic-1',
                'topic': 'Persisted topic',
                'date': date.today().isoformat(),
                'duration': '30 min',
                'duration_minutes': 30,
                'is_completed': False,
            }],
        ).save()
        request = self.request(self.user_id, {'session_id': 'session-1', 'is_completed': True})

        first = StudyPlanDetail().patch(request, str(plan.id))
        second = StudyPlanDetail().patch(request, str(plan.id))

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        persisted_subject = Subject.objects.get(id=self.subject.id, user_id=self.user_id)
        persisted_plan = StudyPlan.objects.get(id=plan.id, user_id=self.user_id)
        self.assertTrue(persisted_subject.topics[0].is_completed)
        self.assertEqual(persisted_subject.topics[0].status, 'completed')
        self.assertTrue(persisted_subject.topics[0].revision_required)
        self.assertTrue(persisted_plan.sessions[0]['is_completed'])

        insights = StudyInsights().get(self.request(self.user_id))
        self.assertEqual(insights.data['completed_topics'], 1)
        self.assertEqual(insights.data['completed_sessions'], 1)
        self.assertEqual(insights.data['total_sessions'], 1)

        foreign_plan_response = StudyPlanDetail().get(self.request(self.other_user_id), str(plan.id))
        self.assertEqual(foreign_plan_response.status_code, 404)
        foreign_patch_response = StudyPlanDetail().patch(
            self.request(self.other_user_id, {'session_id': 'session-1', 'is_completed': False}),
            str(plan.id),
        )
        self.assertEqual(foreign_patch_response.status_code, 404)
        self.assertTrue(Subject.objects.get(id=self.subject.id, user_id=self.user_id).topics[0].is_completed)

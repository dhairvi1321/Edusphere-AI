import uuid
import os
from mongoengine.errors import DoesNotExist, ValidationError as MongoValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.conf import settings
from .models import Subject, SyllabusTopic, Assignment, Exam, StudyPlan
from .serializers import SubjectSerializer, SyllabusTopicSerializer, AssignmentSerializer, ExamSerializer, StudyPlanSerializer
from datetime import datetime, timedelta, date


def uid(request):
    return str(request.user.id)


# ── Subjects ──────────────────────────────────────────────────────────────────

class SubjectListCreate(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        subjects = Subject.objects(user_id=uid(request))
        data = []
        for s in subjects:
            d = SubjectSerializer(s).data
            d['id'] = str(s.id)
            data.append(d)
        return Response(data)

    def post(self, request):
        s = Subject(
            user_id=uid(request),
            name=request.data.get('name', ''),
            description=request.data.get('description', ''),
        )
        s.save()
        d = SubjectSerializer(s).data
        d['id'] = str(s.id)
        return Response(d, status=status.HTTP_201_CREATED)


class SubjectDetail(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get(self, request, pk):
        try:
            return Subject.objects.get(id=pk, user_id=uid(request))
        except (DoesNotExist, MongoValidationError, Exception):
            return None

    def get(self, request, pk):
        s = self._get(request, pk)
        if not s:
            return Response(status=status.HTTP_404_NOT_FOUND)
        d = SubjectSerializer(s).data
        d['id'] = str(s.id)
        return Response(d)

    def put(self, request, pk):
        s = self._get(request, pk)
        if not s:
            return Response(status=status.HTTP_404_NOT_FOUND)
        s.name = request.data.get('name', s.name)
        s.description = request.data.get('description', s.description)
        s.save()
        d = SubjectSerializer(s).data
        d['id'] = str(s.id)
        return Response(d)

    def patch(self, request, pk):
        return self.put(request, pk)

    def delete(self, request, pk):
        s = self._get(request, pk)
        if not s:
            return Response(status=status.HTTP_404_NOT_FOUND)
        s.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SubjectFileUpload(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        try:
            s = Subject.objects.get(id=pk, user_id=str(request.user.id))
        except (DoesNotExist, Exception):
            return Response(status=status.HTTP_404_NOT_FOUND)

        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        upload_dir = os.path.join(settings.BASE_DIR, 'uploads', 'syllabus')
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"{uuid.uuid4()}_{file.name}"
        filepath = os.path.join(upload_dir, filename)
        with open(filepath, 'wb+') as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        file_info = {'name': file.name, 'filename': filename}
        s.syllabus_files.append(file_info)
        s.save()
        d = SubjectSerializer(s).data
        d['id'] = str(s.id)
        return Response(d, status=status.HTTP_201_CREATED)

    def delete(self, request, pk, filename):
        try:
            s = Subject.objects.get(id=pk, user_id=str(request.user.id))
        except (DoesNotExist, Exception):
            return Response(status=status.HTTP_404_NOT_FOUND)
        s.syllabus_files = [f for f in s.syllabus_files if f.get('filename') != filename]
        s.save()
        d = SubjectSerializer(s).data
        d['id'] = str(s.id)
        return Response(d)


# ── Topics (embedded in Subject) ──────────────────────────────────────────────

class TopicListCreate(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        subject_id = request.data.get('subject')
        try:
            s = Subject.objects.get(id=subject_id, user_id=uid(request))
        except (DoesNotExist, MongoValidationError, Exception):
            return Response({'detail': 'Subject not found.'}, status=status.HTTP_404_NOT_FOUND)

        difficulty = request.data.get('difficulty', 'medium')
        if difficulty not in ('easy', 'medium', 'hard'):
            difficulty = 'medium'
        topic = SyllabusTopic(
            id=str(uuid.uuid4()),
            title=request.data.get('title', ''),
            is_completed=False,
            difficulty=difficulty,
        )
        s.topics.append(topic)
        s.save()
        return Response({'id': topic.id, 'subject': str(s.id), 'title': topic.title, 'is_completed': topic.is_completed, 'difficulty': topic.difficulty}, status=status.HTTP_201_CREATED)


class TopicDetail(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _find(self, request, pk):
        subjects = Subject.objects(user_id=uid(request))
        for s in subjects:
            for t in s.topics:
                if t.id == pk:
                    return s, t
        return None, None

    def patch(self, request, pk):
        s, t = self._find(request, pk)
        if not t:
            return Response(status=status.HTTP_404_NOT_FOUND)
        t.is_completed = request.data.get('is_completed', t.is_completed)
        t.title = request.data.get('title', t.title)
        if 'difficulty' in request.data:
            d = request.data['difficulty']
            t.difficulty = d if d in ('easy', 'medium', 'hard') else 'medium'
        s.save()
        return Response({'id': t.id, 'subject': str(s.id), 'title': t.title, 'is_completed': t.is_completed, 'difficulty': t.difficulty or 'medium'})

    def delete(self, request, pk):
        s, t = self._find(request, pk)
        if not t:
            return Response(status=status.HTTP_404_NOT_FOUND)
        s.topics = [x for x in s.topics if x.id != pk]
        s.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Assignments ───────────────────────────────────────────────────────────────

class AssignmentListCreate(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        items = Assignment.objects(user_id=uid(request))
        return Response([AssignmentSerializer(a).data for a in items])

    def post(self, request):
        a = Assignment(
            user_id=uid(request),
            subject_id=request.data.get('subject') or None,
            title=request.data.get('title', ''),
            due_date=request.data.get('due_date') or None,
            priority=request.data.get('priority', 'medium'),
        )
        a.save()
        return Response(AssignmentSerializer(a).data, status=status.HTTP_201_CREATED)


class AssignmentDetail(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get(self, request, pk):
        try:
            return Assignment.objects.get(id=pk, user_id=uid(request))
        except (DoesNotExist, MongoValidationError, Exception):
            return None

    def put(self, request, pk):
        a = self._get(request, pk)
        if not a:
            return Response(status=status.HTTP_404_NOT_FOUND)
        a.title = request.data.get('title', a.title)
        a.subject_id = request.data.get('subject') or None
        a.due_date = request.data.get('due_date') or None
        a.priority = request.data.get('priority', a.priority)
        a.is_completed = request.data.get('is_completed', a.is_completed)
        a.save()
        return Response(AssignmentSerializer(a).data)

    def patch(self, request, pk):
        a = self._get(request, pk)
        if not a:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if 'title' in request.data:
            a.title = request.data['title']
        if 'subject' in request.data:
            a.subject_id = request.data['subject'] or None
        if 'due_date' in request.data:
            a.due_date = request.data['due_date'] or None
        if 'priority' in request.data:
            a.priority = request.data['priority']
        if 'is_completed' in request.data:
            a.is_completed = request.data['is_completed']
        a.save()
        return Response(AssignmentSerializer(a).data)

    def delete(self, request, pk):
        a = self._get(request, pk)
        if not a:
            return Response(status=status.HTTP_404_NOT_FOUND)
        a.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Exams ─────────────────────────────────────────────────────────────────────

class ExamListCreate(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        items = Exam.objects(user_id=uid(request))
        return Response([ExamSerializer(e).data for e in items])

    def post(self, request):
        e = Exam(
            user_id=uid(request),
            subject_id=request.data.get('subject') or None,
            title=request.data.get('title', ''),
            exam_date=request.data.get('exam_date', ''),
            notes=request.data.get('notes', ''),
        )
        e.save()
        return Response(ExamSerializer(e).data, status=status.HTTP_201_CREATED)


class ExamDetail(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get(self, request, pk):
        try:
            return Exam.objects.get(id=pk, user_id=uid(request))
        except (DoesNotExist, MongoValidationError, Exception):
            return None

    def put(self, request, pk):
        e = self._get(request, pk)
        if not e:
            return Response(status=status.HTTP_404_NOT_FOUND)
        e.title = request.data.get('title', e.title)
        e.subject_id = request.data.get('subject') or None
        e.exam_date = request.data.get('exam_date', e.exam_date)
        e.notes = request.data.get('notes', e.notes)
        e.save()
        return Response(ExamSerializer(e).data)

    def patch(self, request, pk):
        e = self._get(request, pk)
        if not e:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if 'title' in request.data:
            e.title = request.data['title']
        if 'subject' in request.data:
            e.subject_id = request.data['subject'] or None
        if 'exam_date' in request.data:
            e.exam_date = request.data['exam_date']
        if 'notes' in request.data:
            e.notes = request.data['notes']
        e.save()
        return Response(ExamSerializer(e).data)

    def delete(self, request, pk):
        e = self._get(request, pk)
        if not e:
            return Response(status=status.HTTP_404_NOT_FOUND)
        e.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Study Plans ───────────────────────────────────────────────────────────────

def _ensure_session_ids(plan):
    """Backfill session_id on sessions that pre-date the field. Returns True if any were added."""
    changed = False
    for s in plan.sessions:
        if not s.get('session_id'):
            s['session_id'] = str(uuid.uuid4())
            changed = True
    return changed


class StudyPlanListCreate(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        plans = list(StudyPlan.objects(user_id=uid(request)).order_by('-created_at'))
        for p in plans:
            if _ensure_session_ids(p):
                p.sessions = list(p.sessions)
                p.save()
        return Response([StudyPlanSerializer(p).data for p in plans])

    def post(self, request):
        title = request.data.get('title', 'My Study Plan')
        start_date = request.data.get('start_date', '')
        end_date = request.data.get('end_date', '')
        daily_hours = str(request.data.get('daily_hours', '2'))
        sessions = request.data.get('sessions', [])

        if not start_date or not end_date:
            return Response({'detail': 'start_date and end_date required.'}, status=status.HTTP_400_BAD_REQUEST)

        plan = StudyPlan(
            user_id=uid(request),
            title=title,
            start_date=start_date,
            end_date=end_date,
            daily_hours=daily_hours,
            sessions=sessions,
        )
        plan.save()
        return Response(StudyPlanSerializer(plan).data, status=status.HTTP_201_CREATED)


class StudyPlanDetail(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get(self, request, pk):
        try:
            return StudyPlan.objects.get(id=pk, user_id=uid(request))
        except (DoesNotExist, MongoValidationError, Exception):
            return None

    def get(self, request, pk):
        p = self._get(request, pk)
        if not p:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if _ensure_session_ids(p):
            p.sessions = list(p.sessions)
            p.save()
        return Response(StudyPlanSerializer(p).data)

    def patch(self, request, pk):
        """Toggle completion of a single session by its session_id."""
        p = self._get(request, pk)
        if not p:
            return Response(status=status.HTTP_404_NOT_FOUND)

        session_id = request.data.get('session_id')
        is_completed = request.data.get('is_completed')

        if not session_id or is_completed is None:
            return Response(
                {'detail': 'session_id and is_completed are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Build a new list so MongoEngine detects the change (in-place dict
        # mutation is not tracked by DictField and would be silently dropped).
        new_sessions = []
        updated = False
        for s in p.sessions:
            entry = dict(s)  # shallow copy so we don't mutate the original
            if entry.get('session_id') == session_id:
                entry['is_completed'] = bool(is_completed)
                updated = True
            new_sessions.append(entry)

        if not updated:
            return Response(
                {'detail': f'Session "{session_id}" not found in this plan.'},
                status=status.HTTP_404_NOT_FOUND
            )

        p.sessions = new_sessions  # reassignment marks the field dirty
        p.save()
        return Response(StudyPlanSerializer(p).data)

    def delete(self, request, pk):
        p = self._get(request, pk)
        if not p:
            return Response(status=status.HTTP_404_NOT_FOUND)
        p.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)



def _build_session_pool(user_id, excluded_topic_ids=None):
    """Return a priority-sorted list of schedulable topic dicts for user_id.
    Topics whose id is in excluded_topic_ids are skipped.
    Completed syllabus topics are always skipped.
    """
    excluded = excluded_topic_ids or set()
    subjects = list(Subject.objects(user_id=user_id))
    exams = list(Exam.objects(user_id=user_id))
    assignments = list(Assignment.objects(user_id=user_id))

    exam_priority = {}
    for exam in exams:
        if not exam.subject_id:
            continue
        try:
            exam_date = datetime.strptime(exam.exam_date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            continue
        current = exam_priority.get(exam.subject_id)
        if current is None or exam_date < current:
            exam_priority[exam.subject_id] = exam_date

    assignment_priority = {}
    for assignment in assignments:
        if assignment.is_completed or not assignment.subject_id:
            continue
        due_date = None
        if assignment.due_date:
            try:
                due_date = datetime.strptime(assignment.due_date, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
        priority_rank = {'high': 0, 'medium': 1, 'low': 2}.get(assignment.priority, 1)
        key = (0 if due_date else 1, due_date or datetime.max.date(), priority_rank)
        sid = assignment.subject_id
        if sid not in assignment_priority or key < assignment_priority[sid]:
            assignment_priority[sid] = key

    DIFFICULTY_RANK = {'hard': 0, 'medium': 1, 'easy': 2}
    pool = []
    for subject in subjects:
        for topic in subject.topics or []:
            if topic.is_completed or topic.id in excluded:
                continue
            sid = str(subject.id)
            pool.append({
                'subject': subject.name,
                'subject_id': sid,
                'topic': topic.title,
                'topic_id': topic.id,
                '_exam_key': exam_priority.get(sid, datetime.max.date()),
                '_assignment_key': assignment_priority.get(sid, (2, datetime.max.date(), 3)),
                '_difficulty_key': DIFFICULTY_RANK.get(topic.difficulty or 'medium', 1),
            })

    pool.sort(key=lambda item: (
        item['_exam_key'],
        item['_assignment_key'],
        item['_difficulty_key'],
        item['topic'].casefold()
    ))
    return pool


def _schedule_sessions(topic_pool, start, end, daily_hours):
    """Distribute topic_pool across [start, end] respecting daily_hours. Returns session list."""
    sessions = []
    topic_index = 0
    session_duration = 45
    daily_minutes = daily_hours * 60
    total_days = (end - start).days + 1

    for day_offset in range(total_days):
        if topic_index >= len(topic_pool):
            break
        current_date = (start + timedelta(days=day_offset)).isoformat()
        minutes_used = 0
        while topic_index < len(topic_pool):
            if minutes_used + session_duration > daily_minutes:
                break
            item = topic_pool[topic_index]
            sessions.append({
                'session_id': str(uuid.uuid4()),
                'date': current_date,
                'subject': item['subject'],
                'subject_id': item['subject_id'],
                'topic': item['topic'],
                'topic_id': item['topic_id'],
                'duration': f'{session_duration} min',
                'duration_minutes': session_duration,
                'is_completed': False,
            })
            minutes_used += session_duration
            topic_index += 1
    return sessions


class RescheduleStudyPlan(APIView):
    """Preview or commit a rescheduled plan for an existing saved plan."""
    permission_classes = [permissions.IsAuthenticated]

    def _get_plan(self, request, pk):
        try:
            return StudyPlan.objects.get(id=pk, user_id=uid(request))
        except (DoesNotExist, MongoValidationError, Exception):
            return None

    def _parse_and_validate(self, request):
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        try:
            daily_hours = int(request.data.get('daily_hours', 2))
        except (TypeError, ValueError):
            return None, None, None, {'detail': 'daily_hours must be a whole number.'}
        if not start_date or not end_date:
            return None, None, None, {'detail': 'start_date and end_date required.'}
        if not 1 <= daily_hours <= 24:
            return None, None, None, {'detail': 'daily_hours must be between 1 and 24.'}
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None, None, None, {'detail': 'Invalid date format. Use YYYY-MM-DD.'}
        if end < start:
            return None, None, None, {'detail': 'end_date must be on or after start_date.'}
        return start, end, daily_hours, None

    def post(self, request, pk):
        """Preview a rescheduled plan without saving.
        Mirrors PUT exactly: keeps completed sessions, replaces all pending ones.
        """
        plan = self._get_plan(request, pk)
        if not plan:
            return Response(status=status.HTTP_404_NOT_FOUND)

        start, end, daily_hours, err = self._parse_and_validate(request)
        if err:
            return Response(err, status=status.HTTP_400_BAD_REQUEST)

        _ensure_session_ids(plan)

        # Only exclude completed topic IDs — same logic as PUT so preview == commit
        completed_sessions = [s for s in plan.sessions if s.get('is_completed')]
        pending_sessions = [s for s in plan.sessions if not s.get('is_completed')]
        completed_topic_ids = {s['topic_id'] for s in completed_sessions if s.get('topic_id')}

        topic_pool = _build_session_pool(uid(request), excluded_topic_ids=completed_topic_ids)
        new_sessions = _schedule_sessions(topic_pool, start, end, daily_hours)

        return Response({
            'plan_id': str(plan.id),
            'preserved_completed': len(completed_sessions),
            'removed_pending': len(pending_sessions),
            'new_sessions': new_sessions,
            'total_new': len(new_sessions),
            'unscheduled_topics': len(topic_pool) - len(new_sessions),
            'message': (
                'Reschedule preview ready. Call PUT to confirm.'
                if new_sessions
                else 'No new incomplete topics to schedule.'
            )
        })

    def put(self, request, pk):
        """Commit the reschedule: keep completed sessions, replace pending with new schedule."""
        plan = self._get_plan(request, pk)
        if not plan:
            return Response(status=status.HTTP_404_NOT_FOUND)

        start, end, daily_hours, err = self._parse_and_validate(request)
        if err:
            return Response(err, status=status.HTTP_400_BAD_REQUEST)

        _ensure_session_ids(plan)

        completed_sessions = [dict(s) for s in plan.sessions if s.get('is_completed')]
        completed_session_topic_ids = {s['topic_id'] for s in completed_sessions if s.get('topic_id')}

        topic_pool = _build_session_pool(uid(request), excluded_topic_ids=completed_session_topic_ids)
        new_sessions = _schedule_sessions(topic_pool, start, end, daily_hours)

        plan.sessions = completed_sessions + new_sessions
        plan.start_date = start.isoformat()
        plan.end_date = end.isoformat()
        plan.daily_hours = str(daily_hours)
        plan.save()

        return Response(StudyPlanSerializer(plan).data)


class StudyInsights(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user_id = uid(request)
        today = date.today()
        today_str = today.isoformat()

        subjects = list(Subject.objects(user_id=user_id))
        assignments = list(Assignment.objects(user_id=user_id))
        exams = list(Exam.objects(user_id=user_id))
        plans = list(StudyPlan.objects(user_id=user_id))

        # Overall session completion
        all_sessions = [s for p in plans for s in (p.sessions or [])]
        total_sessions = len(all_sessions)
        completed_sessions = sum(1 for s in all_sessions if s.get('is_completed'))
        pending_sessions = total_sessions - completed_sessions
        completion_pct = round((completed_sessions / total_sessions) * 100) if total_sessions else 0

        # Upcoming exams (next 7 days)
        upcoming_exams = []
        for e in exams:
            try:
                days = (datetime.strptime(e.exam_date, '%Y-%m-%d').date() - today).days
            except (ValueError, TypeError):
                continue
            if 0 <= days <= 7:
                upcoming_exams.append({'title': e.title, 'exam_date': e.exam_date, 'days_until': days})
        upcoming_exams.sort(key=lambda x: x['days_until'])

        # Urgent assignments (pending, due within 3 days or high priority)
        urgent_assignments = []
        for a in assignments:
            if a.is_completed:
                continue
            days = None
            if a.due_date:
                try:
                    days = (datetime.strptime(a.due_date, '%Y-%m-%d').date() - today).days
                except (ValueError, TypeError):
                    pass
            if (days is not None and days <= 3) or a.priority == 'high':
                urgent_assignments.append({
                    'title': a.title,
                    'due_date': a.due_date,
                    'priority': a.priority,
                    'days_until': days,
                })
        urgent_assignments.sort(key=lambda x: (x['days_until'] if x['days_until'] is not None else 999, x['priority'] != 'high'))

        # Remaining topics by subject
        topics_by_subject = []
        for s in subjects:
            topics = s.topics or []
            remaining = [t.title for t in topics if not t.is_completed]
            if remaining:
                topics_by_subject.append({'subject': s.name, 'remaining': len(remaining), 'total': len(topics)})

        # Daily study progress (today's sessions)
        today_sessions = [s for s in all_sessions if s.get('date') == today_str]
        today_done = sum(1 for s in today_sessions if s.get('is_completed'))

        return Response({
            'completion_pct': completion_pct,
            'completed_sessions': completed_sessions,
            'pending_sessions': pending_sessions,
            'total_sessions': total_sessions,
            'upcoming_exams': upcoming_exams[:3],
            'urgent_assignments': urgent_assignments[:3],
            'topics_by_subject': topics_by_subject,
            'today_total': len(today_sessions),
            'today_done': today_done,
        })


class GenerateStudyPlan(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')

        try:
            daily_hours = int(request.data.get('daily_hours', 2))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'daily_hours must be a whole number.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not start_date or not end_date:
            return Response(
                {'detail': 'start_date and end_date required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not 1 <= daily_hours <= 24:
            return Response(
                {'detail': 'daily_hours must be between 1 and 24.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Invalid date format. Use YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if end < start:
            return Response(
                {'detail': 'end_date must be on or after start_date.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_id = uid(request)
        total_days = (end - start).days + 1
        topic_pool = _build_session_pool(user_id)
        sessions = _schedule_sessions(topic_pool, start, end, daily_hours)

        return Response({
            'sessions': sessions,
            'total_days': total_days,
            'scheduled_topics': len(sessions),
            'unscheduled_topics': len(topic_pool) - len(sessions),
            'message': (
                'Study plan generated successfully.'
                if sessions
                else 'No incomplete syllabus topics found.'
            )
        })

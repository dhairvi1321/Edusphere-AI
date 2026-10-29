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
from . import syllabus_processor


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

        ok, err = syllabus_processor.validate_upload(file)
        if not ok:
            return Response({'detail': err}, status=status.HTTP_400_BAD_REQUEST)

        upload_dir = os.path.join(settings.BASE_DIR, 'uploads', 'syllabus')
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"{uuid.uuid4()}_{file.name}"
        filepath = os.path.join(upload_dir, filename)
        with open(filepath, 'wb+') as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        file_info = {'name': file.name, 'filename': filename, 'uploaded_at': datetime.utcnow().isoformat()}
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


class SyllabusExtract(APIView):
    """POST /subjects/<pk>/files/<filename>/extract/
    Extract and parse topics from an already-uploaded syllabus file.
    Returns structured topics for the student to review before importing.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, filename):
        try:
            s = Subject.objects.get(id=pk, user_id=str(request.user.id))
        except (DoesNotExist, Exception):
            return Response(status=status.HTTP_404_NOT_FOUND)

        # Verify the file belongs to this subject
        file_info = next((f for f in s.syllabus_files if f.get('filename') == filename), None)
        if not file_info:
            return Response({'detail': 'File not found for this subject.'}, status=status.HTTP_404_NOT_FOUND)

        filepath = os.path.join(settings.BASE_DIR, 'uploads', 'syllabus', filename)
        if not os.path.exists(filepath):
            return Response({'detail': 'File missing from storage.'}, status=status.HTTP_404_NOT_FOUND)

        ext = os.path.splitext(filename)[1]
        # Strip the UUID prefix to get the real extension
        original_name = file_info.get('name', filename)
        ext = os.path.splitext(original_name)[1]

        text, warning = syllabus_processor.extract_text(filepath, ext)

        if warning and not text.strip():
            return Response({'detail': warning, 'warning': warning, 'topics': []}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        topics = syllabus_processor.parse_topics(text, subject_name=s.name)

        # Detect potential duplicates against existing topics
        existing_titles = {t.title.strip().lower() for t in (s.topics or [])}
        for t in topics:
            t['is_duplicate'] = t['title'].strip().lower() in existing_titles

        return Response({
            'subject_id': str(s.id),
            'subject_name': s.name,
            'filename': file_info.get('name'),
            'topics': topics,
            'total_found': len(topics),
            'existing_topic_count': len(s.topics or []),
            'warning': warning,
        })


class SyllabusTopicImport(APIView):
    """POST /subjects/<pk>/topics/import/
    Bulk-import reviewed topics into the subject.
    Accepts a list of {title, difficulty, unit} dicts.
    Skips topics whose titles already exist unless skip_duplicates=false.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            s = Subject.objects.get(id=pk, user_id=str(request.user.id))
        except (DoesNotExist, Exception):
            return Response(status=status.HTTP_404_NOT_FOUND)

        incoming = request.data.get('topics', [])
        skip_duplicates = request.data.get('skip_duplicates', True)

        if not isinstance(incoming, list) or not incoming:
            return Response({'detail': 'topics must be a non-empty list.'}, status=status.HTTP_400_BAD_REQUEST)

        existing_titles = {t.title.strip().lower() for t in (s.topics or [])}
        added, skipped = 0, 0

        for item in incoming:
            title = str(item.get('title', '')).strip()
            if not title:
                continue
            if skip_duplicates and title.lower() in existing_titles:
                skipped += 1
                continue
            difficulty = item.get('difficulty', 'medium')
            if difficulty not in ('easy', 'medium', 'hard'):
                difficulty = 'medium'
            topic = SyllabusTopic(
                id=str(uuid.uuid4()),
                title=title,
                is_completed=False,
                difficulty=difficulty,
            )
            s.topics.append(topic)
            existing_titles.add(title.lower())
            added += 1

        s.save()
        d = SubjectSerializer(s).data
        d['id'] = str(s.id)
        return Response({'added': added, 'skipped': skipped, 'subject': d}, status=status.HTTP_201_CREATED)


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



def _build_session_pool(user_id, excluded_topic_ids=None, filter_exam_ids=None, filter_subject_ids=None):
    """Return a priority-sorted list of schedulable topic dicts for user_id.
    Topics whose id is in excluded_topic_ids are skipped.
    Completed syllabus topics are always skipped.
    If filter_exam_ids is set, only subjects linked to those exams are included.
    If filter_subject_ids is set, only those subjects are included.
    """
    excluded = excluded_topic_ids or set()
    subjects = list(Subject.objects(user_id=user_id))
    exams = list(Exam.objects(user_id=user_id))
    assignments = list(Assignment.objects(user_id=user_id))

    # Resolve subject IDs from selected exams and merge with any explicit subject filter
    if filter_exam_ids:
        exam_subject_ids = {e.subject_id for e in exams if str(e.id) in filter_exam_ids and e.subject_id}
        merged = set(filter_subject_ids or []) | exam_subject_ids
        # Only apply the merged filter if it is non-empty; otherwise keep all subjects
        if merged:
            filter_subject_ids = list(merged)

    if filter_subject_ids:
        subjects = [s for s in subjects if str(s.id) in filter_subject_ids]

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


_TOPIC_DURATION = {'easy': 20, 'medium': 30, 'hard': 45}


def _topic_duration(item):
    """Return session duration in minutes based on difficulty rank (0=hard,1=medium,2=easy)."""
    rank = item.get('_difficulty_key', 1)
    return {0: 45, 1: 30, 2: 20}.get(rank, 30)


def _schedule_sessions(topic_pool, start, end, daily_hours):
    """Distribute topic_pool across [start, end] respecting daily_hours. Returns session list."""
    sessions = []
    topic_index = 0
    daily_minutes = daily_hours * 60
    total_days = (end - start).days + 1

    for day_offset in range(total_days):
        if topic_index >= len(topic_pool):
            break
        current_date = (start + timedelta(days=day_offset)).isoformat()
        minutes_used = 0
        while topic_index < len(topic_pool):
            item = topic_pool[topic_index]
            duration = _topic_duration(item)
            if minutes_used + duration > daily_minutes:
                break
            sessions.append({
                'session_id': str(uuid.uuid4()),
                'date': current_date,
                'subject': item['subject'],
                'subject_id': item['subject_id'],
                'topic': item['topic'],
                'topic_id': item['topic_id'],
                'duration': f'{duration} min',
                'duration_minutes': duration,
                'is_completed': False,
            })
            minutes_used += duration
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

        # Build subject id -> name map for exam resolution
        subject_map = {str(s.id): s.name for s in subjects}

        # Overall session completion
        all_sessions = [s for p in plans for s in (p.sessions or [])]
        total_sessions = len(all_sessions)
        completed_sessions = sum(1 for s in all_sessions if s.get('is_completed'))
        pending_sessions = total_sessions - completed_sessions
        session_completion_pct = round((completed_sessions / total_sessions) * 100) if total_sessions else 0

        # Topic-level totals across all subjects
        total_topics = sum(len(s.topics or []) for s in subjects)
        completed_topics = sum(sum(1 for t in (s.topics or []) if t.is_completed) for s in subjects)
        topic_completion_pct = round((completed_topics / total_topics) * 100) if total_topics else 0

        # All upcoming exams (today or future), sorted by date
        upcoming_exams = []
        for e in exams:
            try:
                days = (datetime.strptime(e.exam_date, '%Y-%m-%d').date() - today).days
            except (ValueError, TypeError):
                continue
            if days >= 0:
                upcoming_exams.append({
                    'title': e.title,
                    'subject': subject_map.get(e.subject_id or '', '') or '',
                    'exam_date': e.exam_date,
                    'days_until': days,
                })
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

        # Subject-wise progress (all subjects, including those with 0 topics)
        subject_progress = []
        for s in subjects:
            topics = s.topics or []
            total = len(topics)
            done = sum(1 for t in topics if t.is_completed)
            pct = round((done / total) * 100) if total else 0
            subject_progress.append({
                'subject': s.name,
                'total_topics': total,
                'completed_topics': done,
                'completion_pct': pct,
            })

        # Daily study progress (today's sessions)
        today_sessions = [s for s in all_sessions if s.get('date') == today_str]
        today_done = sum(1 for s in today_sessions if s.get('is_completed'))

        return Response({
            'total_subjects': len(subjects),
            'total_topics': total_topics,
            'completed_topics': completed_topics,
            'topic_completion_pct': topic_completion_pct,
            'total_sessions': total_sessions,
            'completed_sessions': completed_sessions,
            'pending_sessions': pending_sessions,
            'session_completion_pct': session_completion_pct,
            # kept for backward compat
            'completion_pct': session_completion_pct,
            'upcoming_exams': upcoming_exams,
            'urgent_assignments': urgent_assignments[:3],
            'subject_progress': subject_progress,
            # kept for backward compat
            'topics_by_subject': [
                {'subject': sp['subject'], 'remaining': sp['total_topics'] - sp['completed_topics'], 'total': sp['total_topics']}
                for sp in subject_progress if sp['total_topics'] > 0
            ],
            'today_total': len(today_sessions),
            'today_done': today_done,
        })


class GenerateStudyPlan(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

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

        # Optional filters: specific exams and/or subjects
        exam_ids = request.data.getlist('exam_ids') if hasattr(request.data, 'getlist') else request.data.get('exam_ids', [])
        subject_ids = request.data.getlist('subject_ids') if hasattr(request.data, 'getlist') else request.data.get('subject_ids', [])
        if isinstance(exam_ids, str):
            exam_ids = [exam_ids] if exam_ids else []
        if isinstance(subject_ids, str):
            subject_ids = [subject_ids] if subject_ids else []

        topic_pool = _build_session_pool(
            user_id,
            filter_exam_ids=exam_ids or None,
            filter_subject_ids=subject_ids or None,
        )

        # Extra topics from uploaded files (PDF/DOCX/PPTX/TXT)
        extra_topics = []
        file_warnings = []
        for uploaded_file in request.FILES.getlist('files'):
            ok, err = syllabus_processor.validate_upload(uploaded_file)
            if not ok:
                file_warnings.append(f"{uploaded_file.name}: {err}")
                continue
            tmp_path = os.path.join(settings.MEDIA_ROOT, 'syllabus', f"{uuid.uuid4()}_{uploaded_file.name}")
            os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
            try:
                with open(tmp_path, 'wb+') as f:
                    for chunk in uploaded_file.chunks():
                        f.write(chunk)
                ext = os.path.splitext(uploaded_file.name)[1]
                text, warning = syllabus_processor.extract_text(tmp_path, ext)
                if warning:
                    file_warnings.append(f"{uploaded_file.name}: {warning}")
                if text.strip():
                    parsed = syllabus_processor.parse_topics(text, subject_name=uploaded_file.name)
                    if not parsed:
                        file_warnings.append(f"{uploaded_file.name}: No topics could be extracted from this file.")
                    label = uploaded_file.name
                    for t in parsed:
                        extra_topics.append({
                            'subject': label,
                            'subject_id': '',
                            'topic': t['title'],
                            'topic_id': str(uuid.uuid4()),
                            '_exam_key': datetime.max.date(),
                            '_assignment_key': (2, datetime.max.date(), 3),
                            '_difficulty_key': 1,
                        })
                else:
                    file_warnings.append(f"{uploaded_file.name}: File produced no readable text.")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        combined_pool = topic_pool + extra_topics
        total_days = (end - start).days + 1
        sessions = _schedule_sessions(combined_pool, start, end, daily_hours)

        if not sessions:
            if not combined_pool:
                # Diagnose why the pool is empty
                all_subjects = list(Subject.objects(user_id=user_id))
                if subject_ids:
                    matched = [s for s in all_subjects if str(s.id) in subject_ids]
                    if not matched:
                        detail = 'None of the selected subjects were found for your account.'
                    elif all(not (s.topics or []) for s in matched):
                        names = ', '.join(s.name for s in matched)
                        detail = f'The selected subject(s) ({names}) have no topics. Add topics first, or upload a syllabus file.'
                    else:
                        detail = 'All topics in the selected subjects are already marked as completed.'
                elif not all_subjects:
                    detail = 'You have no subjects yet. Add a subject and topics first.'
                elif all(not (s.topics or []) for s in all_subjects):
                    detail = 'None of your subjects have topics. Add topics to a subject first.'
                else:
                    detail = 'All your topics are already marked as completed.'
                if file_warnings:
                    detail += ' File issue(s): ' + '; '.join(file_warnings)
                return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)
            else:
                # Pool has topics but none fit in the date range
                detail = (
                    f'The date range ({start_date} to {end_date}) with {daily_hours}h/day '
                    f'is too short to fit any of the {len(combined_pool)} available topic(s). '
                    'Extend the date range or increase daily hours.'
                )
                return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'sessions': sessions,
            'total_days': total_days,
            'scheduled_topics': len(sessions),
            'unscheduled_topics': len(combined_pool) - len(sessions),
            'file_warnings': file_warnings,
            'message': 'Study plan generated successfully.',
        })

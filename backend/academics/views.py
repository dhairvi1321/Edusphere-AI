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
from datetime import datetime, timedelta


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

        topic = SyllabusTopic(
            id=str(uuid.uuid4()),
            title=request.data.get('title', ''),
            is_completed=False,
        )
        s.topics.append(topic)
        s.save()
        return Response({'id': topic.id, 'subject': str(s.id), 'title': topic.title, 'is_completed': topic.is_completed}, status=status.HTTP_201_CREATED)


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
        s.save()
        return Response({'id': t.id, 'subject': str(s.id), 'title': t.title, 'is_completed': t.is_completed})

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

class StudyPlanListCreate(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        plans = StudyPlan.objects(user_id=uid(request)).order_by('-created_at')
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

    def delete(self, request, pk):
        p = self._get(request, pk)
        if not p:
            return Response(status=status.HTTP_404_NOT_FOUND)
        p.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)



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
        subjects = list(Subject.objects(user_id=user_id))
        exams = list(Exam.objects(user_id=user_id))
        assignments = list(Assignment.objects(user_id=user_id))

        total_days = (end - start).days + 1
        session_duration = 45
        sessions_per_day = (daily_hours * 60) // session_duration

        # Find the nearest upcoming exam for each subject.
        exam_priority = {}

        for exam in exams:
            if not exam.subject_id:
                continue

            try:
                exam_date = datetime.strptime(
                    exam.exam_date, '%Y-%m-%d'
                ).date()
            except (ValueError, TypeError):
                continue

            if exam_date < start:
                continue

            current = exam_priority.get(exam.subject_id)

            if current is None or exam_date < current:
                exam_priority[exam.subject_id] = exam_date

        # Find the most urgent pending assignment for each subject.
        assignment_priority = {}

        for assignment in assignments:
            if assignment.is_completed or not assignment.subject_id:
                continue

            subject_id = assignment.subject_id
            due_date = None

            if assignment.due_date:
                try:
                    due_date = datetime.strptime(
                        assignment.due_date, '%Y-%m-%d'
                    ).date()
                except (ValueError, TypeError):
                    pass

            priority_rank = {
                'high': 0,
                'medium': 1,
                'low': 2
            }.get(assignment.priority, 1)

            # Undated assignments are considered after dated ones.
            key = (
                0 if due_date and due_date <= start else 1,
                due_date or datetime.max.date(),
                priority_rank
            )

            if (
                subject_id not in assignment_priority
                or key < assignment_priority[subject_id]
            ):
                assignment_priority[subject_id] = key

        # Build a pool containing only incomplete topics.
        topic_pool = []

        for subject in subjects:
            for topic in subject.topics or []:
                if topic.is_completed:
                    continue

                subject_id = str(subject.id)
                exam_date = exam_priority.get(subject_id)

                # Subjects with upcoming exams come first.
                exam_key = exam_date or datetime.max.date()

                assignment_key = assignment_priority.get(
                    subject_id,
                    (2, datetime.max.date(), 3)
                )

                topic_pool.append({
                    'subject': subject.name,
                    'subject_id': subject_id,
                    'topic': topic.title,
                    'topic_id': topic.id,
                    '_exam_key': exam_key,
                    '_assignment_key': assignment_key
                })

        # Sort by exam date, assignment urgency, then topic name.
        topic_pool.sort(
            key=lambda item: (
                item['_exam_key'],
                item['_assignment_key'],
                item['topic'].casefold()
            )
        )

        sessions = []
        topic_index = 0

        # Schedule each pending topic at most once.
        # Never cycle back to already scheduled topics.
        for day_offset in range(total_days):
            if topic_index >= len(topic_pool):
                break

            current_date = (
                start + timedelta(days=day_offset)
            ).isoformat()

            for _ in range(sessions_per_day):
                if topic_index >= len(topic_pool):
                    break

                item = topic_pool[topic_index]

                sessions.append({
                    'date': current_date,
                    'subject': item['subject'],
                    'subject_id': item['subject_id'],
                    'topic': item['topic'],
                    'topic_id': item['topic_id'],
                    'duration': f'{session_duration} min',
                    'duration_minutes': session_duration,
                    'is_completed': False
                })

                topic_index += 1

        return Response({
            'sessions': sessions,
            'total_days': total_days,
            'sessions_per_day': sessions_per_day,
            'scheduled_topics': len(sessions),
            'unscheduled_topics': len(topic_pool) - len(sessions),
            'message': (
                'Study plan generated successfully.'
                if sessions
                else 'No incomplete syllabus topics found.'
            )
        })

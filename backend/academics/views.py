import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from .models import Subject, SyllabusTopic, Assignment, Exam
from .serializers import SubjectSerializer, SyllabusTopicSerializer, AssignmentSerializer, ExamSerializer


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

    def _get(self, request, pk):
        try:
            s = Subject.objects.get(id=pk, user_id=uid(request))
            return s
        except Subject.DoesNotExist:
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


# ── Topics (embedded in Subject) ──────────────────────────────────────────────

class TopicListCreate(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        subject_id = request.data.get('subject')
        try:
            s = Subject.objects.get(id=subject_id, user_id=uid(request))
        except Subject.DoesNotExist:
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
        except Assignment.DoesNotExist:
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
        return self.put(request, pk)

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
        except Exam.DoesNotExist:
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
        return self.put(request, pk)

    def delete(self, request, pk):
        e = self._get(request, pk)
        if not e:
            return Response(status=status.HTTP_404_NOT_FOUND)
        e.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

from rest_framework import viewsets, permissions
from .models import Subject, SyllabusTopic, Assignment, Exam
from .serializers import SubjectSerializer, SyllabusTopicSerializer, AssignmentSerializer, ExamSerializer


class OwnerQuerysetMixin:
    """Restrict queryset to objects owned by the requesting user."""
    user_field = 'user'

    def get_queryset(self):
        return self.queryset.filter(**{self.user_field: self.request.user})

    def perform_create(self, serializer):
        serializer.save(**{self.user_field: self.request.user})


class SubjectViewSet(OwnerQuerysetMixin, viewsets.ModelViewSet):
    queryset = Subject.objects.prefetch_related('topics')
    serializer_class = SubjectSerializer
    permission_classes = [permissions.IsAuthenticated]


class SyllabusTopicViewSet(viewsets.ModelViewSet):
    serializer_class = SyllabusTopicSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SyllabusTopic.objects.filter(subject__user=self.request.user)


class AssignmentViewSet(OwnerQuerysetMixin, viewsets.ModelViewSet):
    queryset = Assignment.objects.select_related('subject')
    serializer_class = AssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]


class ExamViewSet(OwnerQuerysetMixin, viewsets.ModelViewSet):
    queryset = Exam.objects.select_related('subject')
    serializer_class = ExamSerializer
    permission_classes = [permissions.IsAuthenticated]

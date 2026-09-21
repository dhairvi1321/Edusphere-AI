from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SubjectViewSet, SyllabusTopicViewSet, AssignmentViewSet, ExamViewSet

router = DefaultRouter()
router.register('subjects', SubjectViewSet, basename='subject')
router.register('topics', SyllabusTopicViewSet, basename='topic')
router.register('assignments', AssignmentViewSet, basename='assignment')
router.register('exams', ExamViewSet, basename='exam')

urlpatterns = [
    path('', include(router.urls)),
]

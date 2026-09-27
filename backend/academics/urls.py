from django.urls import path
from .views import (
    SubjectListCreate,
    SubjectDetail,
    TopicListCreate,
    TopicDetail,
    AssignmentListCreate,
    AssignmentDetail,
    ExamListCreate,
    ExamDetail,
)

urlpatterns = [
    path('subjects/', SubjectListCreate.as_view(), name='subjects'),
    path('subjects/<str:pk>/', SubjectDetail.as_view(), name='subject-detail'),

    path('topics/', TopicListCreate.as_view(), name='topics'),
    path('topics/<str:pk>/', TopicDetail.as_view(), name='topic-detail'),

    path('assignments/', AssignmentListCreate.as_view(), name='assignments'),
    path('assignments/<str:pk>/', AssignmentDetail.as_view(), name='assignment-detail'),

    path('exams/', ExamListCreate.as_view(), name='exams'),
    path('exams/<str:pk>/', ExamDetail.as_view(), name='exam-detail'),
]
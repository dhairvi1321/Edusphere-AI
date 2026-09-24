from django.urls import path
from .views import (
    SubjectListCreate, SubjectDetail,
    TopicListCreate, TopicDetail,
    AssignmentListCreate, AssignmentDetail,
    ExamListCreate, ExamDetail,
)

urlpatterns = [
    path('subjects/', SubjectListCreate.as_view()),
    path('subjects/<str:pk>/', SubjectDetail.as_view()),
    path('topics/', TopicListCreate.as_view()),
    path('topics/<str:pk>/', TopicDetail.as_view()),
    path('assignments/', AssignmentListCreate.as_view()),
    path('assignments/<str:pk>/', AssignmentDetail.as_view()),
    path('exams/', ExamListCreate.as_view()),
    path('exams/<str:pk>/', ExamDetail.as_view()),
]

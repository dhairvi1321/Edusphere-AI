from django.urls import path
from .views import (
    SubjectListCreate,
    SubjectDetail,
    SubjectFileUpload,
    SyllabusExtract,
    SyllabusTopicImport,
    TopicListCreate,
    TopicDetail,
    AssignmentListCreate,
    AssignmentDetail,
    ExamListCreate,
    ExamDetail,
    StudyPlanListCreate,
    StudyPlanDetail,
    GenerateStudyPlan,
    RescheduleStudyPlan,
    StudyInsights,
    AcademicAssistantAsk,
)

urlpatterns = [
    path('subjects/', SubjectListCreate.as_view(), name='subjects'),
    path('subjects/<str:pk>/', SubjectDetail.as_view(), name='subject-detail'),
    path('subjects/<str:pk>/files/', SubjectFileUpload.as_view(), name='subject-files'),
    path('subjects/<str:pk>/files/<str:filename>/', SubjectFileUpload.as_view(), name='subject-file-delete'),
    path('subjects/<str:pk>/files/<str:filename>/extract/', SyllabusExtract.as_view(), name='subject-file-extract'),
    path('subjects/<str:pk>/topics/import/', SyllabusTopicImport.as_view(), name='subject-topics-import'),

    path('topics/', TopicListCreate.as_view(), name='topics'),
    path('topics/<str:pk>/', TopicDetail.as_view(), name='topic-detail'),

    path('assignments/', AssignmentListCreate.as_view(), name='assignments'),
    path('assignments/<str:pk>/', AssignmentDetail.as_view(), name='assignment-detail'),

    path('exams/', ExamListCreate.as_view(), name='exams'),
    path('exams/<str:pk>/', ExamDetail.as_view(), name='exam-detail'),

    path('study-plans/generate/', GenerateStudyPlan.as_view(), name='generate-study-plan'),
    path('study-plans/', StudyPlanListCreate.as_view(), name='study-plans'),
    path('study-plans/<str:pk>/reschedule/', RescheduleStudyPlan.as_view(), name='reschedule-study-plan'),
    path('study-plans/<str:pk>/', StudyPlanDetail.as_view(), name='study-plan-detail'),

    path('insights/', StudyInsights.as_view(), name='study-insights'),
    path('assistant/ask/', AcademicAssistantAsk.as_view(), name='academic-assistant-ask'),
]

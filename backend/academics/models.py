from mongoengine import Document, StringField, BooleanField, DateField, ListField, EmbeddedDocument, EmbeddedDocumentField, DictField
from datetime import datetime, date


class SyllabusTopic(EmbeddedDocument):
    id = StringField()  # client-side generated or set on save
    title = StringField(required=True, max_length=200)
    is_completed = BooleanField(default=False)
    difficulty = StringField(default='medium', choices=('easy', 'medium', 'hard'))


class Subject(Document):
    meta = {'collection': 'subjects'}

    user_id = StringField(required=True)  # stores str(user.id)
    name = StringField(required=True, max_length=100)
    description = StringField(default='')
    topics = ListField(EmbeddedDocumentField(SyllabusTopic), default=list)
    syllabus_files = ListField(DictField(), default=list)  # [{name, url}]
    created_at = DateField(default=date.today)


class Assignment(Document):
    meta = {'collection': 'assignments'}

    PRIORITY_CHOICES = ('low', 'medium', 'high')

    user_id = StringField(required=True)
    subject_id = StringField(default=None)
    title = StringField(required=True, max_length=200)
    due_date = StringField(default=None)   # stored as ISO date string YYYY-MM-DD
    priority = StringField(default='medium', choices=PRIORITY_CHOICES)
    is_completed = BooleanField(default=False)


class Exam(Document):
    meta = {'collection': 'exams'}

    user_id = StringField(required=True)
    subject_id = StringField(default=None)
    title = StringField(required=True, max_length=200)
    exam_date = StringField(required=True)  # YYYY-MM-DD
    notes = StringField(default='')


class StudyPlan(Document):
    meta = {'collection': 'study_plans'}

    user_id = StringField(required=True)
    title = StringField(required=True, max_length=200)
    start_date = StringField(required=True)   # YYYY-MM-DD
    end_date = StringField(required=True)     # YYYY-MM-DD
    daily_hours = StringField(default='2')
    sessions = ListField(DictField(), default=list)  # [{date, subject, topic, duration}]
    created_at = DateField(default=datetime.utcnow)

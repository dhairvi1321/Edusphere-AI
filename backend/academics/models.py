from mongoengine import Document, StringField, BooleanField, DateField, ReferenceField, ListField, EmbeddedDocument, EmbeddedDocumentField, CASCADE
from datetime import datetime


class SyllabusTopic(EmbeddedDocument):
    id = StringField()  # client-side generated or set on save
    title = StringField(required=True, max_length=200)
    is_completed = BooleanField(default=False)


class Subject(Document):
    meta = {'collection': 'subjects'}

    user_id = StringField(required=True)  # stores str(user.id)
    name = StringField(required=True, max_length=100)
    description = StringField(default='')
    topics = ListField(EmbeddedDocumentField(SyllabusTopic), default=list)
    created_at = DateField(default=datetime.utcnow)


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

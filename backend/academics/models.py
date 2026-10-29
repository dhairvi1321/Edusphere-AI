from mongoengine import Document, StringField, BooleanField, DateField, DateTimeField, IntField, ListField, EmbeddedDocument, EmbeddedDocumentField, DictField
from datetime import datetime, date


class SyllabusTopic(EmbeddedDocument):
    id = StringField()  # client-side generated or set on save
    title = StringField(required=True, max_length=200)
    is_completed = BooleanField(default=False)
    difficulty = StringField(default='medium', choices=('easy', 'medium', 'hard'))
    status = StringField(default='not_started', choices=('not_started', 'in_progress', 'completed'))
    revision_required = BooleanField(default=False)


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


class QuizQuestion(EmbeddedDocument):
    question_id = StringField(required=True)
    text = StringField(required=True, max_length=1000)
    options = ListField(StringField(max_length=500), min_length=2, max_length=6)
    correct_index = IntField(required=True, min_value=0, max_value=5)
    explanation = StringField(default='', max_length=2000)
    topic_id = StringField(default=None)  # selected syllabus topic this question covers
    difficulty = StringField(default='medium', choices=('easy', 'medium', 'hard'))


class TopicQuiz(Document):
    meta = {
        'collection': 'topic_quizzes',
        'indexes': ['user_id', ('user_id', 'subject_id', 'topic_id')],
    }

    user_id = StringField(required=True)
    subject_id = StringField(required=True)
    topic_id = StringField(required=True)  # first topic, retained for existing records
    topic_ids = ListField(StringField(), default=list)
    topic_names = ListField(StringField(), default=list)
    title = StringField(required=True, max_length=200)
    source = StringField(default='author_created', choices=('author_created', 'question_bank', 'openai_generated'))
    selection_key = StringField(default=None)
    difficulty = StringField(default='medium', choices=('easy', 'medium', 'hard'))
    questions = ListField(EmbeddedDocumentField(QuizQuestion), default=list)
    created_at = DateTimeField(default=datetime.utcnow)


class QuizAttempt(Document):
    meta = {
        'collection': 'quiz_attempts',
        'indexes': ['user_id', ('user_id', 'quiz_id', '-created_at')],
    }

    user_id = StringField(required=True)
    quiz_id = StringField(required=True)
    subject_id = StringField(required=True)
    topic_id = StringField(required=True)
    topic_ids = ListField(StringField(), default=list)
    quiz_title = StringField(required=True)
    answers = ListField(DictField(), default=list)
    score = IntField(required=True, min_value=0, max_value=100)
    correct_count = IntField(required=True, min_value=0)
    incorrect_count = IntField(required=True, min_value=0)
    total_questions = IntField(required=True, min_value=0)
    created_at = DateTimeField(default=datetime.utcnow)

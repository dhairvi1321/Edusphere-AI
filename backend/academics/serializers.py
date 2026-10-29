from rest_framework import serializers
import uuid


class SyllabusTopicSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    subject = serializers.CharField(read_only=True)  # parent subject id, set in view
    title = serializers.CharField(max_length=200)
    is_completed = serializers.BooleanField(default=False)
    difficulty = serializers.ChoiceField(choices=['easy', 'medium', 'hard'], default='medium')
    status = serializers.ChoiceField(choices=['not_started', 'in_progress', 'completed'], default='not_started')
    revision_required = serializers.BooleanField(default=False)


class SubjectSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(default='', allow_blank=True)
    topics = serializers.SerializerMethodField()
    syllabus_files = serializers.SerializerMethodField()
    created_at = serializers.DateField(read_only=True)

    def get_topics(self, obj):
        return [
            {
                'id': t.id,
                'subject': str(obj.id),
                'title': t.title,
                'is_completed': t.is_completed,
                'difficulty': t.difficulty or 'medium',
                'status': 'completed' if t.is_completed else (
                    getattr(t, 'status', None)
                    if getattr(t, 'status', None) in ('not_started', 'in_progress', 'completed')
                    else 'not_started'
                ),
                'revision_required': bool(getattr(t, 'revision_required', False)),
            }
            for t in (obj.topics or [])
        ]

    def get_syllabus_files(self, obj):
        return list(obj.syllabus_files or [])


class AssignmentSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    subject = serializers.CharField(allow_null=True, allow_blank=True, default=None)
    title = serializers.CharField(max_length=200)
    due_date = serializers.CharField(allow_null=True, allow_blank=True, default=None)
    priority = serializers.ChoiceField(choices=['low', 'medium', 'high'], default='medium')
    is_completed = serializers.BooleanField(default=False)

    def to_representation(self, obj):
        return {
            'id': str(obj.id),
            'subject': obj.subject_id or None,
            'title': obj.title,
            'due_date': obj.due_date,
            'priority': obj.priority,
            'is_completed': obj.is_completed,
        }


class ExamSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    subject = serializers.CharField(allow_null=True, allow_blank=True, default=None)
    title = serializers.CharField(max_length=200)
    exam_date = serializers.CharField()
    notes = serializers.CharField(allow_blank=True, default='')

    def to_representation(self, obj):
        return {
            'id': str(obj.id),
            'subject': obj.subject_id or None,
            'title': obj.title,
            'exam_date': obj.exam_date,
            'notes': obj.notes,
        }


class StudyPlanSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    title = serializers.CharField(max_length=200)
    start_date = serializers.CharField()
    end_date = serializers.CharField()
    daily_hours = serializers.CharField(default='2')
    sessions = serializers.ListField(child=serializers.DictField(), default=list)
    created_at = serializers.DateField(read_only=True)

    def to_representation(self, obj):
        return {
            'id': str(obj.id),
            'title': obj.title,
            'start_date': obj.start_date,
            'end_date': obj.end_date,
            'daily_hours': obj.daily_hours,
            'sessions': list(obj.sessions or []),
            'created_at': str(obj.created_at),
        }


class QuizAnswerSubmissionSerializer(serializers.Serializer):
    question_id = serializers.CharField(max_length=100)
    selected_index = serializers.IntegerField(min_value=0, max_value=5)


class QuizAttemptSubmissionSerializer(serializers.Serializer):
    answers = serializers.ListField(child=QuizAnswerSubmissionSerializer(), allow_empty=False)


def serialize_topic_quiz_summary(quiz, subject, topic):
    topics = topic if isinstance(topic, list) else [topic]
    topic_ids = list(getattr(quiz, 'topic_ids', []) or [quiz.topic_id])
    topic_names = list(getattr(quiz, 'topic_names', []) or [item.title for item in topics])
    return {
        'id': str(quiz.id),
        'title': quiz.title,
        'subject_id': str(subject.id),
        'subject_name': subject.name,
        'topic_id': topic_ids[0],
        'topic_ids': topic_ids,
        'topic_name': ', '.join(topic_names),
        'topic_names': topic_names,
        'question_count': len(quiz.questions or []),
        'source': quiz.source,
        'difficulty': getattr(quiz, 'difficulty', 'medium'),
    }


def serialize_topic_quiz_questions(quiz, subject, topic):
    """Return attemptable questions without answer keys or correctness data."""
    data = serialize_topic_quiz_summary(quiz, subject, topic)
    data['questions'] = [
        {'question_id': question.question_id, 'text': question.text, 'options': list(question.options or []), 'topic_id': question.topic_id or quiz.topic_id}
        for question in (quiz.questions or [])
    ]
    return data


def serialize_quiz_attempt(attempt):
    return {
        'id': str(attempt.id),
        'quiz_id': attempt.quiz_id,
        'subject_id': attempt.subject_id,
        'topic_id': attempt.topic_id,
        'topic_ids': list(attempt.topic_ids or [attempt.topic_id]),
        'quiz_title': attempt.quiz_title,
        'score': attempt.score,
        'correct_count': attempt.correct_count,
        'incorrect_count': attempt.incorrect_count,
        'total_questions': attempt.total_questions,
        'created_at': attempt.created_at.isoformat() if attempt.created_at else None,
        'answers': list(attempt.answers or []),
    }

from rest_framework import serializers
import uuid


class SyllabusTopicSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    subject = serializers.CharField(read_only=True)  # parent subject id, set in view
    title = serializers.CharField(max_length=200)
    is_completed = serializers.BooleanField(default=False)


class SubjectSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(default='', allow_blank=True)
    topics = serializers.SerializerMethodField()
    created_at = serializers.DateField(read_only=True)

    def get_topics(self, obj):
        return [
            {'id': t.id, 'subject': str(obj.id), 'title': t.title, 'is_completed': t.is_completed}
            for t in (obj.topics or [])
        ]


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

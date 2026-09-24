from rest_framework import serializers
from .models import Subject, SyllabusTopic, Assignment, Exam


class SyllabusTopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyllabusTopic
        fields = ('id', 'subject', 'title', 'is_completed')


class SubjectSerializer(serializers.ModelSerializer):
    topics = SyllabusTopicSerializer(many=True, read_only=True)

    class Meta:
        model = Subject
        fields = ('id', 'name', 'description', 'topics', 'created_at')
        read_only_fields = ('created_at',)


class AssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = ('id', 'subject', 'title', 'due_date', 'priority', 'is_completed')


class ExamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exam
        fields = ('id', 'subject', 'title', 'exam_date', 'notes')

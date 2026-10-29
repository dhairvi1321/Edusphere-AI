"""Import a curated multiple-choice question set for one existing student topic."""
import json
from uuid import uuid4

from django.core.management.base import BaseCommand, CommandError
from mongoengine.errors import DoesNotExist, ValidationError as MongoValidationError

from academics.models import QuizQuestion, Subject, TopicQuiz


class Command(BaseCommand):
    help = "Create or replace a curated quiz for a student's existing syllabus topic from a JSON file."

    def add_arguments(self, parser):
        parser.add_argument('--user-id', required=True, help='Mongo user id that owns the subject/topic.')
        parser.add_argument('--subject-id', required=True, help='Existing Mongo subject id.')
        parser.add_argument('--topic-id', required=True, help='Existing embedded syllabus topic id.')
        parser.add_argument('--file', required=True, help='UTF-8 JSON question bank file.')

    def handle(self, *args, **options):
        try:
            with open(options['file'], 'r', encoding='utf-8') as stream:
                payload = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f'Could not read quiz JSON: {exc}') from exc

        title = payload.get('title') if isinstance(payload, dict) else None
        questions = payload.get('questions') if isinstance(payload, dict) else None
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 200:
            raise CommandError('Quiz JSON must contain a title of 1 to 200 characters.')
        if not isinstance(questions, list) or not 1 <= len(questions) <= 50:
            raise CommandError('Quiz JSON must contain 1 to 50 questions.')

        normalized_questions = []
        for index, item in enumerate(questions, start=1):
            if not isinstance(item, dict):
                raise CommandError(f'Question {index} must be a JSON object.')
            text = item.get('question')
            options_list = item.get('options')
            correct_index = item.get('correct_index')
            explanation = item.get('explanation', '')
            difficulty = item.get('difficulty', 'medium')
            if not isinstance(text, str) or not text.strip() or len(text.strip()) > 1000:
                raise CommandError(f'Question {index} must contain 1 to 1000 characters of text.')
            if not isinstance(options_list, list) or not 2 <= len(options_list) <= 6:
                raise CommandError(f'Question {index} must contain 2 to 6 answer options.')
            if any(not isinstance(option, str) or not option.strip() or len(option.strip()) > 500 for option in options_list):
                raise CommandError(f'Question {index} options must be non-empty strings of at most 500 characters.')
            clean_options = [option.strip() for option in options_list]
            if len({option.casefold() for option in clean_options}) != len(clean_options):
                raise CommandError(f'Question {index} contains duplicate answer options.')
            if isinstance(correct_index, bool) or not isinstance(correct_index, int) or not 0 <= correct_index < len(clean_options):
                raise CommandError(f'Question {index} correct_index must point to one of its options.')
            if not isinstance(explanation, str) or len(explanation) > 2000:
                raise CommandError(f'Question {index} explanation must be at most 2000 characters.')
            if not isinstance(difficulty, str) or difficulty.lower() not in ('easy', 'medium', 'hard'):
                raise CommandError(f'Question {index} difficulty must be Easy, Medium, or Hard.')
            normalized_questions.append(QuizQuestion(
                question_id=str(uuid4()),
                text=text.strip(),
                options=clean_options,
                correct_index=correct_index,
                explanation=explanation.strip(),
                difficulty=difficulty.lower(),
            ))

        try:
            subject = Subject.objects.get(id=options['subject_id'], user_id=options['user_id'])
        except (DoesNotExist, MongoValidationError) as exc:
            raise CommandError('The specified subject does not belong to that user or does not exist.') from exc
        topic = next((item for item in (subject.topics or []) if item.id == options['topic_id']), None)
        if not topic:
            raise CommandError('The specified topic does not exist in that subject.')

        quiz = TopicQuiz.objects(
            user_id=options['user_id'],
            subject_id=str(subject.id),
            topic_id=topic.id,
            title=title.strip(),
        ).modify(
            upsert=True,
            new=True,
            set__source='author_created',
            set__questions=normalized_questions,
            set__topic_ids=[topic.id],
        )
        self.stdout.write(self.style.SUCCESS(
            f'Imported {len(normalized_questions)} author-created question(s) into quiz "{quiz.title}" for {subject.name} / {topic.title}.'
        ))

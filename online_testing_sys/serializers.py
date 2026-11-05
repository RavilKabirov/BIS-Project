
from rest_framework import serializers
from django.utils import timezone
from django.db import transaction

from .models import (
    User,
    Test,
    Question,
    AnswerOption,
    TestAttempt,
    StudentAnswer,
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "user_id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
        ]
        read_only_fields = ["user_id"]


class AnswerOptionSerializer(serializers.ModelSerializer):
    """Public serializer: does not reveal which option is correct."""

    class Meta:
        model = AnswerOption
        fields = ["option_id", "question", "option_text"]
        read_only_fields = ["option_id"]


class TeacherAnswerOptionSerializer(serializers.ModelSerializer):
    """Use this serializer only for teacher/admin operations."""

    class Meta:
        model = AnswerOption
        fields = [
            "option_id",
            "question",
            "option_text",
            "is_correct",
        ]
        read_only_fields = ["option_id"]


class QuestionSerializer(serializers.ModelSerializer):
    options = AnswerOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            "question_id",
            "test",
            "question_text",
            "question_type",
            "points",
            "options",
        ]
        read_only_fields = ["question_id"]

    def validate(self, attrs):
        question_type = attrs.get(
            "question_type",
            getattr(self.instance, "question_type", None),
        )

        if question_type == Question.QuestionType.TEXT:
            if self.instance and self.instance.options.exists():
                raise serializers.ValidationError(
                    "Remove existing answer options before changing "
                    "the question type to text."
                )

        return attrs


class TestSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Test
        fields = [
            "test_id",
            "title",
            "description",
            "created_by",
            "time_limit_minutes",
            "status",
            "questions",
        ]
        read_only_fields = ["test_id", "created_by"]

    def validate_time_limit_minutes(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "Time limit must be at least one minute."
            )
        return value


class TestAttemptSerializer(serializers.ModelSerializer):
    student = UserSerializer(read_only=True)
    test_title = serializers.CharField(
        source="test.title",
        read_only=True,
    )

    class Meta:
        model = TestAttempt
        fields = [
            "attempt_id",
            "test",
            "test_title",
            "student",
            "started_at",
            "submitted_at",
            "score",
            "status",
        ]
        read_only_fields = [
            "attempt_id",
            "student",
            "started_at",
            "submitted_at",
            "score",
            "status",
        ]


class StudentAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAnswer
        fields = [
            "student_answer_id",
            "attempt",
            "question",
            "selected_option",
            "answer_text",
            "is_correct",
            "points_awarded",
        ]
        read_only_fields = [
            "student_answer_id",
            "is_correct",
            "points_awarded",
        ]

    def validate(self, attrs):
        attempt = attrs.get(
            "attempt",
            getattr(self.instance, "attempt", None),
        )
        question = attrs.get(
            "question",
            getattr(self.instance, "question", None),
        )
        option = attrs.get(
            "selected_option",
            getattr(self.instance, "selected_option", None),
        )
        answer_text = attrs.get(
            "answer_text",
            getattr(self.instance, "answer_text", None),
        )

        request = self.context.get("request")

        if attempt and request:
            if attempt.student_id != request.user.pk:
                raise serializers.ValidationError(
                    "You can only submit answers for your own attempts."
                )

        if attempt and attempt.status != TestAttempt.Status.IN_PROGRESS:
            raise serializers.ValidationError(
                "This attempt has already been submitted."
            )

        if attempt and question and question.test_id != attempt.test_id:
            raise serializers.ValidationError(
                "The question must belong to the test being attempted."
            )

        if option and question and option.question_id != question.question_id:
            raise serializers.ValidationError(
                "The selected option must belong to this question."
            )

        if question:
            if question.question_type == Question.QuestionType.MULTIPLE_CHOICE:
                if option is None:
                    raise serializers.ValidationError(
                        {"selected_option": "Select an answer option."}
                    )
            elif question.question_type == Question.QuestionType.TEXT:
                if not answer_text or not answer_text.strip():
                    raise serializers.ValidationError(
                        {"answer_text": "Enter a text answer."}
                    )
                if option is not None:
                    raise serializers.ValidationError(
                        "Text questions must not have a selected option."
                    )

        return attrs


class SubmitAttemptSerializer(serializers.Serializer):
    """Validates a request to submit an attempt."""

    attempt_id = serializers.IntegerField()

    def validate_attempt_id(self, value):
        request = self.context.get("request")

        try:
            attempt = TestAttempt.objects.get(
                attempt_id=value,
                student=request.user,
            )
        except TestAttempt.DoesNotExist:
            raise serializers.ValidationError(
                "Attempt not found."
            )

        if attempt.status != TestAttempt.Status.IN_PROGRESS:
            raise serializers.ValidationError(
                "This attempt has already been submitted."
            )

        self.context["attempt"] = attempt
        return value

    @transaction.atomic
    def save(self, **kwargs):
        attempt = self.context["attempt"]

        # Calculate the result from stored answers.
        answers = attempt.answers.select_related(
            "question",
            "selected_option",
        )

        earned_points = 0
        total_points = sum(
            answer.question.points for answer in answers
        )

        for answer in answers:
            correct = (
                answer.selected_option is not None
                and answer.selected_option.is_correct
            )

            # Automatic grading for multiple-choice questions.
            if answer.question.question_type == Question.QuestionType.MULTIPLE_CHOICE:
                answer.is_correct = correct
                answer.points_awarded = (
                    answer.question.points if correct else 0
                )
                answer.save(
                    update_fields=["is_correct", "points_awarded"]
                )
                earned_points += answer.points_awarded

            # Text answers need a separate grading process.
            elif answer.question.question_type == Question.QuestionType.TEXT:
                if answer.is_correct is True:
                    earned_points += answer.points_awarded

        score = (
            earned_points / total_points * 100
            if total_points > 0
            else 0
        )

        attempt.score = round(score, 2)
        attempt.status = TestAttempt.Status.SUBMITTED
        attempt.submitted_at = timezone.now()
        attempt.save(
            update_fields=["score", "status", "submitted_at"]
        )

        return attempt

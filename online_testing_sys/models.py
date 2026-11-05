from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError


class User(AbstractUser):
    user_id = models.AutoField(primary_key=True)
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        TEACHER = "teacher", "Teacher"

    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )

    def __str__(self):
        return f"{self.username} ({self.role})"


class Test(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    test_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_tests",
    )
    time_limit_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    def clean(self):
        super().clean()
        if self.created_by_id and self.created_by.role != User.Role.TEACHER:
            raise ValidationError({
                "created_by": "Only a teacher can create a test."
            })

    def __str__(self):
        return self.title


class Question(models.Model):
    class QuestionType(models.TextChoices):
        MULTIPLE_CHOICE = "multiple_choice", "Multiple choice"
        TEXT = "text", "Text answer"

    question_id = models.AutoField(primary_key=True)
    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    question_text = models.TextField()
    question_type = models.CharField(
        max_length=30,
        choices=QuestionType.choices,
        default=QuestionType.MULTIPLE_CHOICE,
    )
    points = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(0)],
    )

    def __str__(self):
        return f"{self.test.title}: {self.question_text[:50]}"


class AnswerOption(models.Model):
    option_id = models.AutoField(primary_key=True)
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="options",
    )
    option_text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.option_text[:80]


class TestAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        SUBMITTED = "submitted", "Submitted"

    attempt_id = models.AutoField(primary_key=True)
    test = models.ForeignKey(
        Test,
        on_delete=models.PROTECT,
        related_name="attempts",
    )
    student = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="test_attempts",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )

    def clean(self):
        super().clean()
        if self.student_id and self.student.role != User.Role.STUDENT:
            raise ValidationError({
                "student": "Only a student can take a test."
            })

    def __str__(self):
        return f"{self.student.username} - {self.test.title}"


class StudentAnswer(models.Model):
    student_answer_id = models.AutoField(primary_key=True)
    attempt = models.ForeignKey(
        TestAttempt,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        related_name="student_answers",
    )
    selected_option = models.ForeignKey(
        AnswerOption,
        on_delete=models.PROTECT,
        related_name="selected_answers",
        null=True,
        blank=True,
    )
    answer_text = models.TextField(null=True, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    points_awarded = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question"],
                name="unique_question_per_attempt",
            )
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.attempt_id and self.question_id:
            if self.question.test_id != self.attempt.test_id:
                errors["question"] = (
                    "The question must belong to the test being attempted."
                )

        if self.selected_option_id and self.question_id:
            if self.selected_option.question_id != self.question_id:
                errors["selected_option"] = (
                    "The selected option must belong to this question."
                )

        if self.attempt_id and self.attempt.status == TestAttempt.Status.SUBMITTED:
            errors["attempt"] = "Cannot modify answers after submission."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"Answer by {self.attempt.student.username} "
            f"to question {self.question_id}"
        )

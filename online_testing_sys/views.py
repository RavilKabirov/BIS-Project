
from django.shortcuts import get_object_or_404
from django.db import transaction

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import BasePermission, IsAuthenticated

from .models import (
    User,
    Test,
    Question,
    TestAttempt,
    StudentAnswer,
)
from .serializers import (
    TestSerializer,
    QuestionSerializer,
    TestAttemptSerializer,
    StudentAnswerSerializer,
    SubmitAttemptSerializer,
)


# ---------- Permissions ----------

class IsTeacher(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == User.Role.TEACHER
        )


class IsStudent(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == User.Role.STUDENT
        )


class IsTeacherOwner(BasePermission):
    """Object-level permission: teacher must own the test."""

    def has_object_permission(self, request, view, obj):
        return (
            request.user.role == User.Role.TEACHER
            and obj.created_by_id == request.user.pk
        )


# ---------- Tests ----------

class TestListCreateView(generics.ListCreateAPIView):
    serializer_class = TestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.role == User.Role.TEACHER:
            return Test.objects.filter(
                created_by=user
            ).prefetch_related("questions__options")

        return Test.objects.filter(
            status=Test.Status.PUBLISHED
        ).prefetch_related("questions__options")

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsTeacher()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class TestDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TestSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "test_id"

    def get_queryset(self):
        user = self.request.user

        if user.role == User.Role.TEACHER:
            return Test.objects.filter(
                created_by=user
            ).prefetch_related("questions__options")

        return Test.objects.filter(
            status=Test.Status.PUBLISHED
        ).prefetch_related("questions__options")

    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH", "DELETE"]:
            return [IsAuthenticated(), IsTeacher()]
        return [IsAuthenticated()]


# ---------- Questions ----------

class QuestionListCreateView(generics.ListCreateAPIView):
    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticated]

    def get_test(self):
        return get_object_or_404(
            Test,
            test_id=self.kwargs["test_id"],
        )

    def get_queryset(self):
        test = self.get_test()
        user = self.request.user

        if user.role == User.Role.TEACHER:
            if test.created_by_id != user.pk:
                return Question.objects.none()
        elif test.status != Test.Status.PUBLISHED:
            return Question.objects.none()

        return Question.objects.filter(
            test=test
        ).prefetch_related("options")

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsTeacher()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        test = self.get_test()

        if (
            request.user.role != User.Role.TEACHER
            or test.created_by_id != request.user.pk
        ):
            return Response(
                {"detail": "You cannot add questions to this test."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(test=test)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )


class QuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "question_id"

    def get_queryset(self):
        user = self.request.user
        queryset = Question.objects.select_related("test").prefetch_related(
            "options"
        )

        if user.role == User.Role.TEACHER:
            return queryset.filter(test__created_by=user)

        return queryset.filter(test__status=Test.Status.PUBLISHED)

    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH", "DELETE"]:
            return [IsAuthenticated(), IsTeacher()]
        return [IsAuthenticated()]

    def perform_update(self, serializer):
        question = self.get_object()
        if question.test.created_by_id != self.request.user.pk:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                "You cannot edit another teacher's question."
            )
        serializer.save()

    def perform_destroy(self, instance):
        if instance.test.created_by_id != self.request.user.pk:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                "You cannot delete another teacher's question."
            )
        instance.delete()


# ---------- Starting a test attempt ----------

class StartAttemptView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, test_id):
        test = get_object_or_404(
            Test,
            test_id=test_id,
            status=Test.Status.PUBLISHED,
        )

        # Business rule: no retake after a submitted attempt.
        submitted_attempt_exists = TestAttempt.objects.filter(
            student=request.user,
            test=test,
            status=TestAttempt.Status.SUBMITTED,
        ).exists()

        if submitted_attempt_exists:
            return Response(
                {
                    "detail": (
                        "You have already submitted this test "
                        "and cannot retake it."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_attempt = TestAttempt.objects.filter(
            student=request.user,
            test=test,
            status=TestAttempt.Status.IN_PROGRESS,
        ).first()

        if existing_attempt:
            return Response(
                TestAttemptSerializer(existing_attempt).data,
                status=status.HTTP_200_OK,
            )

        attempt = TestAttempt.objects.create(
            student=request.user,
            test=test,
        )

        return Response(
            TestAttemptSerializer(attempt).data,
            status=status.HTTP_201_CREATED,
        )


# ---------- Answers in an attempt ----------

class AttemptAnswerListCreateView(generics.ListCreateAPIView):
    serializer_class = StudentAnswerSerializer
    permission_classes = [IsAuthenticated, IsStudent]

    def get_attempt(self):
        return get_object_or_404(
            TestAttempt,
            attempt_id=self.kwargs["attempt_id"],
            student=self.request.user,
        )

    def get_queryset(self):
        attempt = self.get_attempt()
        return StudentAnswer.objects.filter(
            attempt=attempt
        ).select_related("question", "selected_option")

    def create(self, request, *args, **kwargs):
        attempt = self.get_attempt()

        if attempt.status != TestAttempt.Status.IN_PROGRESS:
            return Response(
                {"detail": "This attempt has already been submitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # The attempt is taken from the URL, not trusted from the client.
        data = request.data.copy()
        data["attempt"] = attempt.pk

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        # Prevent duplicate answers for the same question in this attempt.
        question = serializer.validated_data["question"]
        if StudentAnswer.objects.filter(
            attempt=attempt,
            question=question,
        ).exists():
            return Response(
                {
                    "detail": (
                        "An answer for this question already exists. "
                        "Use PATCH to update it."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )


class AttemptAnswerDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = StudentAnswerSerializer
    permission_classes = [IsAuthenticated, IsStudent]
    lookup_field = "student_answer_id"

    def get_queryset(self):
        return StudentAnswer.objects.filter(
            attempt__student=self.request.user,
            attempt__attempt_id=self.kwargs["attempt_id"],
            attempt__status=TestAttempt.Status.IN_PROGRESS,
        )

    def update(self, request, *args, **kwargs):
        answer = self.get_object()

        data = request.data.copy()
        data["attempt"] = answer.attempt_id
        data["question"] = answer.question_id

        serializer = self.get_serializer(
            answer,
            data=data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

from .models import AnswerOption
from .serializers import AnswerOptionSerializer, TeacherAnswerOptionSerializer


class AnswerOptionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_question(self):
        return get_object_or_404(
            Question.objects.select_related("test"),
            question_id=self.kwargs["question_id"],
        )

    def get_queryset(self):
        question = self.get_question()

        if self.request.user.role == User.Role.TEACHER:
            if question.test.created_by_id != self.request.user.pk:
                return AnswerOption.objects.none()
        elif question.test.status != Test.Status.PUBLISHED:
            return AnswerOption.objects.none()

        return AnswerOption.objects.filter(question=question)

    def get_serializer_class(self):
        if self.request.user.role == User.Role.TEACHER:
            return TeacherAnswerOptionSerializer

        return AnswerOptionSerializer

    def create(self, request, *args, **kwargs):
        question = self.get_question()

        if (
            request.user.role != User.Role.TEACHER
            or question.test.created_by_id != request.user.pk
        ):
            return Response(
                {"detail": "You do not have permission to add options."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(question=question)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )
# ---------- Submitting a test ----------

class SubmitAttemptView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, attempt_id):
        serializer = SubmitAttemptSerializer(
            data={"attempt_id": attempt_id},
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        attempt = serializer.save()

        return Response(
            TestAttemptSerializer(attempt).data,
            status=status.HTTP_200_OK,
        )


# ---------- Viewing results ----------

class MyAttemptsView(generics.ListAPIView):
    serializer_class = TestAttemptSerializer
    permission_classes = [IsAuthenticated, IsStudent]

    def get_queryset(self):
        return TestAttempt.objects.filter(
            student=self.request.user
        ).select_related("student", "test")


class TeacherTestResultsView(generics.ListAPIView):
    serializer_class = TestAttemptSerializer
    permission_classes = [IsAuthenticated, IsTeacher]

    def get_queryset(self):
        test = get_object_or_404(
            Test,
            test_id=self.kwargs["test_id"],
            created_by=self.request.user,
        )

        return TestAttempt.objects.filter(
            test=test,
            status=TestAttempt.Status.SUBMITTED,
        ).select_related("student", "test")

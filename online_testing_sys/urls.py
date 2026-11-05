
from django.urls import path

from .views import (
    TestListCreateView,
    TestDetailView,
    QuestionListCreateView,
    QuestionDetailView,
    AnswerOptionListCreateView,
    StartAttemptView,
    AttemptAnswerListCreateView,
    AttemptAnswerDetailView,
    SubmitAttemptView,
    MyAttemptsView,
    TeacherTestResultsView,
)

urlpatterns = [
    # Tests
    path("tests/", TestListCreateView.as_view(), name="test-list"),
    path(
        "tests/<int:test_id>/",
        TestDetailView.as_view(),
        name="test-detail",
    ),

    # Questions
    path(
        "tests/<int:test_id>/questions/",
        QuestionListCreateView.as_view(),
        name="question-list",
    ),
    path(
        "questions/<int:question_id>/",
        QuestionDetailView.as_view(),
        name="question-detail",
    ),

    # Answer options
    path(
        "questions/<int:question_id>/options/",
        AnswerOptionListCreateView.as_view(),
        name="option-list",
    ),

    # Student attempts and answers
    path(
        "tests/<int:test_id>/start/",
        StartAttemptView.as_view(),
        name="start-attempt",
    ),
    path(
        "attempts/<int:attempt_id>/answers/",
        AttemptAnswerListCreateView.as_view(),
        name="attempt-answers",
    ),
    path(
        "attempts/<int:attempt_id>/answers/<int:student_answer_id>/",
        AttemptAnswerDetailView.as_view(),
        name="attempt-answer-detail",
    ),
    path(
        "attempts/<int:attempt_id>/submit/",
        SubmitAttemptView.as_view(),
        name="submit-attempt",
    ),

    # Results
    path(
        "my-attempts/",
        MyAttemptsView.as_view(),
        name="my-attempts",
    ),
    path(
        "tests/<int:test_id>/results/",
        TeacherTestResultsView.as_view(),
        name="teacher-test-results",
    ),
]

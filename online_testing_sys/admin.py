from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    User,
    Test,
    Question,
    AnswerOption,
    TestAttempt,
    StudentAnswer,
)


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ("question_text", "question_type", "points")


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 2
    fields = ("option_text", "is_correct")


class StudentAnswerInline(admin.TabularInline):
    model = StudentAnswer
    extra = 0
    fields = (
        "question",
        "selected_option",
        "answer_text",
        "is_correct",
        "points_awarded",
    )
    readonly_fields = ("is_correct", "points_awarded")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "user_id",
        "username",
        "first_name",
        "last_name",
        "email",
        "role",
        "is_staff",
        "is_active",
    )
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("user_id",)

    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Testing System", {"fields": ("user_id", "role")}),
    )

    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Testing System", {"fields": ("email", "role")}),
    )

    readonly_fields = ("user_id",)


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = (
        "test_id",
        "title",
        "created_by",
        "status",
        "time_limit_minutes",
    )
    list_filter = ("status",)
    search_fields = ("title", "description", "created_by__username")
    ordering = ("test_id",)
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "question_id",
        "question_text",
        "test",
        "question_type",
        "points",
    )
    list_filter = ("question_type", "test")
    search_fields = ("question_text", "test__title")
    ordering = ("question_id",)
    inlines = [AnswerOptionInline]


@admin.register(AnswerOption)
class AnswerOptionAdmin(admin.ModelAdmin):
    list_display = (
        "option_id",
        "option_text",
        "question",
        "is_correct",
    )
    list_filter = ("is_correct", "question__test")
    search_fields = ("option_text", "question__question_text")
    ordering = ("option_id",)


@admin.register(TestAttempt)
class TestAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "attempt_id",
        "test",
        "student",
        "status",
        "score",
        "started_at",
        "submitted_at",
    )
    list_filter = ("status", "test")
    search_fields = ("student__username", "test__title")
    ordering = ("-started_at",)
    readonly_fields = ("started_at",)
    inlines = [StudentAnswerInline]


@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "student_answer_id",
        "attempt",
        "question",
        "selected_option",
        "is_correct",
        "points_awarded",
    )
    list_filter = ("is_correct", "attempt__test")
    search_fields = (
        "attempt__student__username",
        "question__question_text",
        "answer_text",
    )
    ordering = ("student_answer_id",)
    readonly_fields = ("is_correct", "points_awarded")

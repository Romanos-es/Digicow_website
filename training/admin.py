from django.contrib import admin

from .models import Attendance, County, Topic, TrainingSession


@admin.register(County)
class CountyAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("title", "active", "created_by", "created_at")
    list_filter = ("active",)
    search_fields = ("title", "summary")


class AttendanceInline(admin.TabularInline):
    model = Attendance
    extra = 0
    autocomplete_fields = ("farmer",)


@admin.register(TrainingSession)
class TrainingSessionAdmin(admin.ModelAdmin):
    list_display = ("topic", "county", "trainer", "venue", "date", "status")
    list_filter = ("status", "county", "date")
    search_fields = ("topic__title", "venue")
    inlines = [AttendanceInline]


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("farmer", "session", "status", "registered_at")
    list_filter = ("status",)

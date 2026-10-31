from django.contrib import admin

from .models import QACall


@admin.register(QACall)
class QACallAdmin(admin.ModelAdmin):
    list_display = ("attendance", "outcome", "rating", "agent", "called_at")
    list_filter = ("outcome", "agent")
    search_fields = ("attendance__farmer__full_name", "attendance__farmer__phone", "feedback")

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User
from training.models import Farmer


@admin.register(User)
class DigicowUserAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "role", "phone", "is_active")
    list_filter = ("role", "is_active")
    fieldsets = UserAdmin.fieldsets + (("Digicow", {"fields": ("role", "phone")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Digicow", {"fields": ("first_name", "last_name", "email", "role", "phone")}),
    )


@admin.register(Farmer)
class FarmerAccountAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "county", "location", "farm_focus", "user", "registered_by")
    list_filter = ("county",)
    search_fields = ("full_name", "phone", "location", "user__username")

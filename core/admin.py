from django.contrib import admin

from .models import ContactMessage, FarmerReview


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "created_at", "handled")
    list_filter = ("handled",)
    search_fields = ("name", "phone", "email", "message")


@admin.register(FarmerReview)
class FarmerReviewAdmin(admin.ModelAdmin):
    list_display = ("farmer_name", "training_title", "rating", "is_published", "created_at")
    list_filter = ("is_published", "rating", "created_at")
    search_fields = ("attendance__farmer__full_name", "comment")
    readonly_fields = ("attendance", "rating", "comment", "created_at")
    actions = ("publish_reviews", "unpublish_reviews")

    @admin.display(description="Farmer")
    def farmer_name(self, review):
        return review.attendance.farmer.full_name

    @admin.display(description="Training")
    def training_title(self, review):
        return review.attendance.session.topic.title

    @admin.action(description="Publish selected farmer reviews")
    def publish_reviews(self, request, queryset):
        queryset.update(is_published=True)

    @admin.action(description="Hide selected farmer reviews")
    def unpublish_reviews(self, request, queryset):
        queryset.update(is_published=False)

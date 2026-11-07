from django.contrib import admin

from .models import Brand, Order, OrderItem, Product


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "active", "website_url")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "unit", "price", "active")
    list_filter = ("brand", "active")
    search_fields = ("name", "description")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "farmer", "trainer", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("farmer__full_name", "farmer__phone")
    inlines = [OrderItemInline]

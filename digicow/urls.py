from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Digicow administration"
admin.site.site_title = "Digicow admin"
admin.site.index_title = "Manage Digicow"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("training/", include("training.urls")),
    path("qa/", include("qa.urls")),
    path("shop/", include("shop.urls")),
    path("", include("core.urls")),
]

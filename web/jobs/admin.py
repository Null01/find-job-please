from django.contrib import admin
from django.utils.html import format_html

from .models import CV, Job, Owner


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "gender", "birth_date", "created_at")
    search_fields = ("email", "full_name")


@admin.register(CV)
class CVAdmin(admin.ModelAdmin):
    list_display = ("email", "owner", "filename", "is_active", "analyzed_at", "uploaded_at")
    list_filter = ("is_active",)
    search_fields = ("email",)
    readonly_fields = ("uploaded_at", "keywords", "analyzed_at")


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "owner", "status", "is_favorite", "match_score",
                    "site", "is_remote", "date_posted", "open_link")
    list_filter = ("owner", "status", "is_favorite", "site", "is_remote", "job_type")
    list_editable = ("status", "is_favorite")
    search_fields = ("title", "company", "location", "description")
    ordering = ("-match_score", "-date_posted")
    list_per_page = 50

    @admin.display(description="Abrir")
    def open_link(self, obj):
        return format_html('<a href="{}" target="_blank">↗</a>', obj.job_url)

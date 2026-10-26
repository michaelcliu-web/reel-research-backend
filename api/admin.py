from django.contrib import admin
from django.contrib import messages

from .models import CustomUser
import csv
from django.http import HttpResponse


class CustomUserAdmin(admin.ModelAdmin):
    actions = ["export_as_csv", "export_emails"]

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def has_delete_permission(self, request, obj=None):
        if obj is not None:
            return super().has_delete_permission(request, obj)
        return False

    list_display = (
        "email",
        "first_name",
        "last_name",
        "date_joined",
        "id",
        "email_verified",
        "clerk_id",
        "banned",
        "onboarded",
        "is_staff",
        "is_superuser",
    )

    ordering = ("-date_joined",)
    list_per_page = 50
    show_full_result_count = False
    search_fields = ("email", "clerk_id", "first_name", "last_name")
    list_filter = (
        "email_verified",
        "banned",
        "onboarded",
        "is_staff",
        "is_superuser",
        ("date_joined", admin.DateFieldListFilter),
    )

    readonly_fields = (
        "id",
        "date_joined",
        "last_login",
    )

    fieldsets = (
        ("Identity", {
            "fields": ("id", "email", "email_verified", "clerk_id", "first_name", "last_name")
        }),
        ("Account Status", {
            "fields": ("banned", "onboarded", "is_active", "is_staff", "is_superuser", "last_login", "date_joined")
        }),
    )

    @admin.action(description="Export user emails")
    def export_emails(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename=user_emails.csv'
        writer = csv.writer(response)
        writer.writerow(["email"])
        for user in queryset:
            writer.writerow([user.email])
        self.message_user(request, f"Exported {queryset.count()} email(s).", messages.SUCCESS)
        return response

    def export_as_csv(self, request, queryset):
        meta = self.model._meta
        field_names = [field.name for field in meta.fields]
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename={meta.model_name}.csv'
        writer = csv.writer(response)
        writer.writerow(field_names)
        for obj in queryset:
            row = [getattr(obj, field) for field in field_names]
            writer.writerow(row)
        return response
    export_as_csv.short_description = "Export Selected as CSV"


admin.site.register(CustomUser, CustomUserAdmin)

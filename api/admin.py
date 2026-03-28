from django.contrib import admin
from django.utils import timezone
from payments.admin import SubscriptionInline
from django.contrib import messages

from .models import CustomUser
import csv
from django.http import HttpResponse


class CustomUserAdmin(admin.ModelAdmin):
    inlines = [SubscriptionInline]
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
        "subscribed_display",
        "subscription_plan_display",
        "subscribed_until_display",
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
    list_select_related = ('subscription',)
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
        "subscribed_display",
        "subscription_plan_display",
        "subscribed_until_display",
    )

    fieldsets = (
        ("Identity", {
            "fields": ("id", "email", "email_verified", "clerk_id", "first_name", "last_name")
        }),
        ("Account Status", {
            "fields": ("banned", "onboarded", "is_active", "is_staff", "is_superuser", "last_login", "date_joined")
        }),
        ("Subscription (read-only)", {
            "fields": ("subscribed_display", "subscription_plan_display", "subscribed_until_display")
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

    def subscribed_display(self, obj):
        return bool(getattr(obj, "subscribed", False))
    subscribed_display.boolean = True
    subscribed_display.short_description = "Subscribed"

    def subscription_plan_display(self, obj):
        return getattr(obj, "subscription_plan", None) or "—"
    subscription_plan_display.short_description = "Plan"

    def subscribed_until_display(self, obj):
        dt = getattr(obj, "subscribed_until", None)
        return timezone.localtime(dt) if dt else "—"
    subscribed_until_display.short_description = "Subscribed Until"

    def export_as_csv(self, request, queryset):
        meta = self.model._meta
        field_names = [field.name for field in meta.fields]
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename={meta.model_name}.csv'
        writer = csv.writer(response)
        writer.writerow(field_names + ["subscribed", "subscription_plan", "subscribed_until"])
        for obj in queryset:
            row = [getattr(obj, field) for field in field_names]
            row.extend([
                bool(getattr(obj, "subscribed", False)),
                getattr(obj, "subscription_plan", None) or "",
                getattr(obj, "subscribed_until", None) or "",
            ])
            writer.writerow(row)
        return response
    export_as_csv.short_description = "Export Selected as CSV"


admin.site.register(CustomUser, CustomUserAdmin)

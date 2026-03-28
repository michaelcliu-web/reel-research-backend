from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Subscription



class SubscriptionInline(admin.StackedInline):
    model = Subscription
    can_delete = True
    fk_name = "user"
    extra = 0

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user_email',
        'plan_badge',
        'status_badge',
        'cancel_status',
        'billing_period',
        'stripe_ids',
        'created_at',
    )
    list_filter = (
        'plan', 
        'status', 
        'cancel_at_period_end',
        'created_at',
        'current_period_end'
    )
    search_fields = (
        'user__email', 
        'user__id',
        'stripe_customer_id', 
        'stripe_subscription_id',
        'stripe_price_id'
    )
    readonly_fields = (
        'id',
        'stripe_customer_id',
        'stripe_subscription_id',
        'stripe_price_id',
        'created_at',
        'updated_at',
        'current_period_start',
        'current_period_end',
        'cancelled_at',
        'usage_reset_date',
        'formatted_stripe_links',
        'subscription_details',
    )
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'id')
        }),
        ('Subscription Details', {
            'fields': (
                'plan',
                'status',
                'cancel_at_period_end',
                'subscription_details',
            )
        }),
        ('Billing Period', {
            'fields': (
                'current_period_start',
                'current_period_end',
                'cancelled_at',
            )
        }),
        ('Stripe Information', {
            'fields': (
                'stripe_customer_id',
                'stripe_subscription_id',
                'stripe_price_id',
                'formatted_stripe_links',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    ordering = ('-created_at',)
    list_per_page = 50
    
    def user_email(self, obj):
        if obj.user:
            # Don't make this a link - just return the email
            return obj.user.email
        return '-'
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'
    
    def plan_badge(self, obj):
        colors = {
            'free': '#6B7280',
            'plus_monthly': '#3B82F6',
            'plus_yearly': '#2563EB',
            'pro_monthly': '#8B5CF6',
            'pro_yearly': '#7C3AED',
        }
        color = colors.get(obj.plan, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; border-radius: 4px; font-weight: 500;">{}</span>',
            color,
            obj.get_plan_display()
        )
    plan_badge.short_description = 'Plan'
    
    def status_badge(self, obj):
        colors = {
            'active': '#10B981',
            'cancelled': '#EF4444',
            'past_due': '#F59E0B',
            'trialing': '#3B82F6',
            'incomplete': '#6B7280',
            'incomplete_expired': '#DC2626',
        }
        color = colors.get(obj.status, '#6B7280')
        
        icon = ''
        if obj.status == 'active':
            icon = '✓ '
        elif obj.status == 'cancelled':
            icon = '✗ '
        elif obj.status == 'past_due':
            icon = '⚠ '
            
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; border-radius: 4px; font-weight: 500;">{}{}</span>',
            color,
            icon,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def cancel_status(self, obj):
        if obj.cancel_at_period_end:
            return format_html(
                '<span style="color: #DC2626; font-weight: 500;">⏱ Cancelling</span>'
            )
        elif obj.status == 'cancelled':
            return format_html(
                '<span style="color: #6B7280;">Cancelled</span>'
            )
        return format_html(
            '<span style="color: #10B981;">Active</span>'
        )
    cancel_status.short_description = 'Cancel Status'
    
   
    
    def billing_period(self, obj):
        if obj.current_period_end:
            from django.utils import timezone
            days_left = (obj.current_period_end - timezone.now()).days
            
            if days_left < 0:
                status = format_html('<span style="color: #EF4444;">Expired</span>')
            elif days_left <= 3:
                status = format_html('<span style="color: #F59E0B;">{} days left</span>', days_left)
            else:
                status = format_html('<span style="color: #6B7280;">{} days left</span>', days_left)
                
            return format_html(
                '{}<br><small style="color: #9CA3AF;">Ends: {}</small>',
                status,
                obj.current_period_end.strftime('%b %d, %Y')
            )
        return '-'
    billing_period.short_description = 'Billing Period'
    
    def stripe_ids(self, obj):
        links = []
        if obj.stripe_customer_id:
            links.append(format_html(
                '<a href="https://dashboard.stripe.com/customers/{}" target="_blank" '
                'style="color: #3B82F6; text-decoration: none;">Customer ↗</a>',
                obj.stripe_customer_id
            ))
        if obj.stripe_subscription_id:
            links.append(format_html(
                '<a href="https://dashboard.stripe.com/subscriptions/{}" target="_blank" '
                'style="color: #3B82F6; text-decoration: none;">Subscription ↗</a>',
                obj.stripe_subscription_id
            ))
        return mark_safe(' | '.join(links)) if links else '-'
    stripe_ids.short_description = 'Stripe Links'
    
    def formatted_stripe_links(self, obj):
        """Detailed Stripe links for the detail view"""
        links = []
        if obj.stripe_customer_id:
            links.append(format_html(
                '<div style="margin-bottom: 8px;">'
                '<strong>Customer:</strong> '
                '<a href="https://dashboard.stripe.com/customers/{}" target="_blank">{}</a>'
                '</div>',
                obj.stripe_customer_id, obj.stripe_customer_id
            ))
        if obj.stripe_subscription_id:
            links.append(format_html(
                '<div style="margin-bottom: 8px;">'
                '<strong>Subscription:</strong> '
                '<a href="https://dashboard.stripe.com/subscriptions/{}" target="_blank">{}</a>'
                '</div>',
                obj.stripe_subscription_id, obj.stripe_subscription_id
            ))
        if obj.stripe_price_id:
            links.append(format_html(
                '<div><strong>Price ID:</strong> {}</div>',
                obj.stripe_price_id
            ))
        return mark_safe(''.join(links)) if links else 'No Stripe data'
    formatted_stripe_links.short_description = 'Stripe Links'
    
    def subscription_details(self, obj):
        """Formatted subscription details for detail view"""
        details = []
        
        # Is Active
        is_active_display = '✓ Yes' if obj.is_active else '✗ No'
        is_active_color = '#10B981' if obj.is_active else '#EF4444'
        details.append(format_html(
            '<div style="margin-bottom: 8px;">'
            '<strong>Is Active:</strong> '
            '<span style="color: {}; font-weight: 500;">{}</span>'
            '</div>',
            is_active_color, is_active_display
        ))
        
        # Cancel at period end
        if obj.cancel_at_period_end:
            details.append(format_html(
                '<div style="margin-bottom: 8px; color: #DC2626;">'
                '<strong>⚠ Scheduled to cancel at period end</strong>'
                '</div>'
            ))
        
        # Cancelled at
        if obj.cancelled_at:
            details.append(format_html(
                '<div style="margin-bottom: 8px;">'
                '<strong>Cancelled at:</strong> {}'
                '</div>',
                obj.cancelled_at.strftime('%Y-%m-%d %H:%M:%S')
            ))
            
        return mark_safe(''.join(details))
    subscription_details.short_description = 'Subscription Status Details'
    
    
    
    def has_add_permission(self, request):
        # Prevent manual creation of subscriptions
        return False
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user')
    
    actions = ['cancel_subscriptions', 'reactivate_subscriptions']
    
    def cancel_subscriptions(self, request, queryset):
        count = 0
        for subscription in queryset:
            if subscription.status == 'active' and not subscription.cancel_at_period_end:
                subscription.cancel_at_period_end = True
                subscription.save()
                count += 1
        self.message_user(request, f'{count} subscriptions set to cancel.')
    cancel_subscriptions.short_description = 'Set selected subscriptions to cancel at period end'
    
    def reactivate_subscriptions(self, request, queryset):
        count = 0
        for subscription in queryset:
            if subscription.cancel_at_period_end:
                subscription.cancel_at_period_end = False
                subscription.save()
                count += 1
        self.message_user(request, f'{count} subscriptions reactivated.')
    reactivate_subscriptions.short_description = 'Reactivate selected subscriptions'
from django.urls import path
from .views import (
    StripeCheckoutView,
    StripeWebhook,
    StripePortalView,
    VerifyCheckoutSession,
    StripeCancelSubscriptionView,
    StripeReactivateSubscriptionView,
    StripeSwitchPlanView,
)

urlpatterns = [
    path("create-checkout-session/", StripeCheckoutView.as_view(), name="create_checkout_session"),
    path("create-portal-session/", StripePortalView.as_view(), name="create_portal_session"),
    path("cancel-subscription/", StripeCancelSubscriptionView.as_view(), name="cancel_subscription"),
    path("reactivate-subscription/", StripeReactivateSubscriptionView.as_view(), name="reactivate_subscription"),
    path("switch-plan/", StripeSwitchPlanView.as_view(), name="switch_plan"),
    path("webhook/", StripeWebhook.as_view(), name="stripe_webhook"),
    path("verify-checkout/", VerifyCheckoutSession.as_view(), name="verify_checkout"),
]

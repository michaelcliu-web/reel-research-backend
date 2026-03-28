from rest_framework import serializers
from .models import CustomUser


class CustomUserSerializer(serializers.ModelSerializer):
    subscription = serializers.SerializerMethodField()

    def get_subscription(self, obj):
        data = {}
        subscription = obj.get_active_subscription()
        data["subscribed"] = True if subscription else False
        if subscription:
            if subscription.current_period_end:
                data["subscribed_until"] = subscription.current_period_end.strftime(
                    "%Y-%m-%d"
                )
            else:
                data["subscribed_until"] = None
            data["subscription_type"] = subscription.plan
        return data

    class Meta:
        model = CustomUser
        fields = (
            "id",
            "email",
            "email_verified",
            "first_name",
            "last_name",
            "subscribed",
            "subscribed_until",
            "subscription",
            "date_joined",
            "onboarded",
        )

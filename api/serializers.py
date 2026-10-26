from rest_framework import serializers
from .models import CustomUser


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = (
            "id",
            "email",
            "email_verified",
            "first_name",
            "last_name",
            "date_joined",
            "onboarded",
        )

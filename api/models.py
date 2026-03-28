import uuid
from django.db import models
from django.contrib.auth.models import (
    UserManager,
    AbstractBaseUser,
    PermissionsMixin,
)
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from rest_framework.authtoken.models import Token


class UserManager(UserManager):
    def _create_user(self, email, password, **extra_fields):
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(null=True, blank=True, unique=True)
    email_verified = models.BooleanField(default=False)
    clerk_id = models.CharField(max_length=250, null=True, blank=True, unique=True)
    first_name = models.CharField(max_length=150, blank=True, default="")
    last_name = models.CharField(max_length=150, blank=True, default="")
    banned = models.BooleanField(default=False)
    onboarded = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    last_login = models.DateTimeField(blank=True, null=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.email or str(self.id)

    def get_active_subscription(self):
        from payments.models import Subscription
        try:
            subscription = self.subscription
            if subscription.is_active:
                return subscription
        except Subscription.DoesNotExist:
            pass
        return None

    @property
    def subscribed(self):
        from payments.models import Subscription
        try:
            subscription = self.subscription
            return subscription.is_active
        except Subscription.DoesNotExist:
            return False

    @property
    def subscription_plan(self):
        from payments.models import Subscription
        try:
            subscription = self.subscription
            if subscription.is_active:
                return subscription.plan
        except Subscription.DoesNotExist:
            pass
        return None

    @property
    def subscribed_until(self):
        from payments.models import Subscription
        try:
            subscription = self.subscription
            if subscription.is_active:
                return subscription.current_period_end
        except Subscription.DoesNotExist:
            pass
        return None

    @receiver(post_save, sender=settings.AUTH_USER_MODEL)
    def create_auth_token(sender, instance=None, created=False, **kwargs):
        if not Token.objects.filter(user=instance).exists():
            Token.objects.create(user=instance)

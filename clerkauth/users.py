from api.models import CustomUser
from clerkauth.tokens import get_email_from_payload


def resolve_user(payload):
    """Return the user for a decoded Clerk token, creating or linking one if needed.

    Looks up by clerk_id first so the Clerk API is only called for users we
    haven't linked yet. Returns None if no email can be found for a new user.
    """
    clerk_id = payload.get("sub")

    try:
        user = CustomUser.objects.get(clerk_id=clerk_id)
    except CustomUser.DoesNotExist:
        email = get_email_from_payload(payload)
        if not email:
            return None

        # Link an existing account by email, or auto-create one for a new Clerk user
        user, _ = CustomUser.objects.get_or_create(email=email)
        user.clerk_id = clerk_id
        user.email_verified = True
        user.save(update_fields=["clerk_id", "email_verified"])
        return user

    if not user.email_verified:
        user.email_verified = True
        user.save(update_fields=["email_verified"])
    return user


def jwt_get_username_from_payload_handler(payload):
    """drf-jwt hook: resolve the Clerk user and return the username it looks up."""
    user = resolve_user(payload)
    if user is None:
        raise Exception("No email found for Clerk user")
    return user.email

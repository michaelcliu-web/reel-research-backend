from django.contrib.auth.models import AnonymousUser
from api.models import CustomUser
from rest_framework.authtoken.models import Token
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from clerkauth.utils import jwt_decode_token, _get_email_from_payload


@database_sync_to_async
def get_user(token_key):
    try:
        decoded_token = jwt_decode_token(token_key)
        clerk_id = decoded_token.get("sub")

        try:
            return CustomUser.objects.get(clerk_id=clerk_id)
        except CustomUser.DoesNotExist:
            email = _get_email_from_payload(decoded_token)
            if email:
                # Try finding by email, update clerk_id if found
                try:
                    user = CustomUser.objects.get(email=email)
                    user.clerk_id = clerk_id
                    user.save(update_fields=["clerk_id"])
                    return user
                except CustomUser.DoesNotExist:
                    pass

                # Auto-create user if they exist in Clerk but not in DB
                user = CustomUser.objects.create(
                    email=email,
                    clerk_id=clerk_id,
                    email_verified=True,
                )
                return user
            return None
    except CustomUser.DoesNotExist:
        return None
    except Exception as e:
        print(f"WebSocket auth error: {e}")
        return None


class TokenAuthMiddleware(BaseMiddleware):
    def __init__(self, inner):
        super().__init__(inner)

    async def __call__(self, scope, receive, send):
        token_key = None
        try:
            query_string = scope["query_string"].decode()
            token_key = dict((x.split("=") for x in query_string.split("&"))).get("token", None)
        except ValueError:
            pass

        user = None
        if token_key:
            user = await get_user(token_key)

        scope["user"] = user if user else AnonymousUser()

        return await super().__call__(scope, receive, send)

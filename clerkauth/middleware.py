from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from clerkauth.tokens import jwt_decode_token
from clerkauth.users import resolve_user


@database_sync_to_async
def get_user(token_key):
    try:
        return resolve_user(jwt_decode_token(token_key))
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

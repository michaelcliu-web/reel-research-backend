from unittest import mock

from django.test import TestCase

from api.models import CustomUser
from clerkauth.users import resolve_user, jwt_get_username_from_payload_handler


@mock.patch("clerkauth.users.get_email_from_payload")
class ResolveUserTests(TestCase):
    def test_known_clerk_id_skips_email_lookup(self, get_email):
        user = CustomUser.objects.create(email="a@example.com", clerk_id="user_1", email_verified=True)

        self.assertEqual(resolve_user({"sub": "user_1"}), user)
        get_email.assert_not_called()

    def test_links_existing_account_by_email(self, get_email):
        get_email.return_value = "a@example.com"
        user = CustomUser.objects.create(email="a@example.com")

        resolved = resolve_user({"sub": "user_1"})

        self.assertEqual(resolved, user)
        user.refresh_from_db()
        self.assertEqual(user.clerk_id, "user_1")
        self.assertTrue(user.email_verified)

    def test_creates_new_user(self, get_email):
        get_email.return_value = "new@example.com"

        user = resolve_user({"sub": "user_2"})

        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(user.clerk_id, "user_2")
        self.assertTrue(user.email_verified)

    def test_no_email_for_new_user_returns_none(self, get_email):
        get_email.return_value = None

        self.assertIsNone(resolve_user({"sub": "user_3"}))
        self.assertFalse(CustomUser.objects.exists())

    def test_rest_handler_returns_email(self, get_email):
        CustomUser.objects.create(email="a@example.com", clerk_id="user_1")

        self.assertEqual(jwt_get_username_from_payload_handler({"sub": "user_1"}), "a@example.com")

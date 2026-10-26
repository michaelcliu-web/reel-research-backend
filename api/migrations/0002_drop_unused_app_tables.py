from django.db import migrations


class Migration(migrations.Migration):
    """Drop tables left behind by removed apps (payments, allauth, django-otp)."""

    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            """
            DROP TABLE IF EXISTS
                payments_subscription,
                account_emailconfirmation,
                account_emailaddress,
                socialaccount_socialtoken,
                socialaccount_socialaccount,
                socialaccount_socialapp_sites,
                socialaccount_socialapp,
                otp_static_statictoken,
                otp_static_staticdevice,
                otp_totp_totpdevice;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

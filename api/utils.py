import environ


def report_to_sentry(error):
    env = environ.Env()
    try:
        import sentry_sdk
        if env("ENVIRONMENT", default="LOCAL") != "LOCAL":
            sentry_sdk.capture_exception(error)
    except ImportError:
        pass

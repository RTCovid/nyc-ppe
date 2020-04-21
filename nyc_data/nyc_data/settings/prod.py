from nyc_data.settings.common import *
import dj_database_url
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

DEBUG = True if os.environ.get("DJANGO_DEBUG", "") == "True" else False

DATABASES["default"] = dj_database_url.config(conn_max_age=600, ssl_require=True)

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN", ""), integrations=[DjangoIntegration()],
)

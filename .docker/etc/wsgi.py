import os
import sys

OUR_DIR = os.path.abspath(os.path.dirname(__file__))

APPS_DIR = os.path.join(OUR_DIR, "apps")

sys.path.insert(0, APPS_DIR)

from django.core.wsgi import get_wsgi_application  # noqa: E402

os.environ["DJANGO_SETTINGS_MODULE"] = "mainsite.settings_local"

application = get_wsgi_application()

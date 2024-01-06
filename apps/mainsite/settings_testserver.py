# It doesn't seem as if this file is still being used.
# TODO: Remove if true
from mainsite.settings import *  # noqa: F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'badgr',
        'OPTIONS': {
            # Uncomment when using MySQL to ensure consistency across servers
            # "init_command": "SET storage_engine=InnoDB",
        },
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
        'LOCATION': '127.0.0.1:11211',
        'KEY_PREFIX': 'test_badgr_',
        'VERSION': 1,
    }
}


# django test speedups
PASSWORD_HASHERS = (
    'django.contrib.auth.hashers.MD5PasswordHasher',
)
DEBUG = False
try:
    logging.disable(logging.CRITICAL)  # noqa: F405
except NameError:
    print("logging undefined!")

# EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"

CELERY_ALWAYS_EAGER = True
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
BROKER_BACKEND = 'memory'

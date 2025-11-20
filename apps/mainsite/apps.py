from django.apps import AppConfig


class BadgrConfig(AppConfig):
    name = "mainsite"

    def ready(self):
        import mainsite.openapi  # noqa: F401

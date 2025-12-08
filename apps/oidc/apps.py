from django.apps import AppConfig


class OidcConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "oidc"

    def ready(self):
        import oidc.openapi  # noqa: F401

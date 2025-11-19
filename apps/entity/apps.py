from django.apps import AppConfig


class EntityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "entity"

    def ready(self):
        import entity.openapi  # noqa: F401

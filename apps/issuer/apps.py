from django.apps import AppConfig


class IssuerConfig(AppConfig):
    name = "issuer"

    def ready(self):
        from issuer.jsonld_loader import setup_jsonld_loader

        setup_jsonld_loader()

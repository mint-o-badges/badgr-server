from django.conf import settings


# TODO: Use email related to the new domain, when one is created. Not urgent in this phase.
def extra_settings(request):
    return {
        "HELP_EMAIL": getattr(settings, "HELP_EMAIL", "info@opensenselab.org"),
        "PINGDOM_MONITORING_ID": getattr(settings, "PINGDOM_MONITORING_ID", None),
        "GOOGLE_ANALYTICS_ID": getattr(settings, "GOOGLE_ANALYTICS_ID", None),
    }

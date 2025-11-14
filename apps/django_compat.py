"""
Compatibility layer for Django 4.x with old packages that expect Django 3.x APIs
"""

# Add back removed translation functions
import django.utils.translation as translation

if not hasattr(translation, "ugettext_lazy"):
    translation.ugettext_lazy = translation.gettext_lazy

if not hasattr(translation, "ugettext"):
    translation.ugettext = translation.gettext

if not hasattr(translation, "ugettext_noop"):
    translation.ugettext_noop = translation.gettext_noop

if not hasattr(translation, "ungettext"):
    translation.ungettext = translation.ngettext

# Add back removed URL function
import django.conf.urls
from django.urls import re_path

if not hasattr(django.conf.urls, "url"):
    django.conf.urls.url = re_path

# Add back force_text
import django.utils.encoding

if not hasattr(django.utils.encoding, "force_text"):
    django.utils.encoding.force_text = django.utils.encoding.force_str

print("✓ Django 3.x compatibility layer loaded for legacy packages")

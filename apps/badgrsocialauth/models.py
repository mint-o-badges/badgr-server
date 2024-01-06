import json

from django.conf import settings
from django.db import models
from django.shortcuts import reverse
from django.utils import timezone
from badgeuser.models import BadgeUser
from .utils import custom_settings_filtered_values


class Saml2Configuration(models.Model):
    metadata_conf_url = models.URLField(verbose_name="Metadata Configuration URL",
                                        help_text="The URL for the XML configuration "
                                        "for SAML2 flows. Get this from the Identity "
                                        "Provider Application.")
    cached_metadata = models.TextField(
        default='', blank=True,
        help_text="If the XML is provided here we avoid making a network request to the metadata_conf_url.")
    slug = models.CharField(max_length=32, unique=True,
            help_text="This slug must be prefixed with saml2.")
    use_signed_authn_request = models.BooleanField(default=False)
    custom_settings = models.TextField(
        default='{}', blank=True,
        help_text="Valid JSON for claim names accepted for local values like email, first_name, last_name")

    def __str__(self):
        return self.slug

    def acs_url(self):
        if not self.slug:
            return ""
        return "{}{}".format(
            getattr(settings, 'HTTP_ORIGIN', ''),
            reverse('assertion_consumer_service', kwargs={'idp_name': self.slug})
        )

    def sp_metadata_url(self):
        if not self.slug:
            return ""
        return "{}{}".format(
            getattr(settings, 'HTTP_ORIGIN', ''),
            reverse('saml2_sp_metadata', kwargs={'idp_name': self.slug})
        )

    @property
    def custom_settings_data(self):
        try:
            return json.loads(self.custom_settings)
        except (TypeError, ValueError,):
            return dict()

    def save(self, **kwargs):
        self.custom_settings = custom_settings_filtered_values(self.custom_settings)
        return super(Saml2Configuration, self).save(**kwargs)


class Saml2Account(models.Model):
    user = models.ForeignKey(BadgeUser,
                             on_delete=models.CASCADE)
    config = models.ForeignKey(Saml2Configuration,
                               on_delete=models.CASCADE)
    uuid = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return "{} on {}".format(self.uuid, self.config)

    @property
    def uid(self):
        return self.uuid

    @property
    def account_identifier(self):
        return 'saml2.{}'.format(self.pk)

    @property
    def provider(self):
        return self.config.slug

    @property
    def date_joined(self):
        # TODO add a migration for this model to have created_at / updated_at fields via inheritance.
        return timezone.now()

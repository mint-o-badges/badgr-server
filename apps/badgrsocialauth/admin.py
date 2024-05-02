import json

from django import forms
from django.contrib.admin import ModelAdmin
from mainsite.admin import badgr_admin

from .models import Saml2Account, Saml2Configuration


class Saml2ConfigurationAdminForm(forms.ModelForm):

    class Meta:
        model = Saml2Configuration
        fields = (
            "metadata_conf_url",
            "cached_metadata",
            "slug",
            "use_signed_authn_request",
            "custom_settings",
        )

    def clean(self):
        custom_settings = self.cleaned_data.get("custom_settings")
        try:
            data = json.loads(custom_settings)
            if not isinstance(data, dict):
                raise ValueError()
        except (
            TypeError,
            ValueError,
        ):
            raise forms.ValidationError(
                "custom_settings must be a valid JSON. email, first_name, and last_name keys are valid."
            )

        return self.cleaned_data


class Saml2ConfigurationModelAdmin(ModelAdmin):
    form = Saml2ConfigurationAdminForm
    readonly_fields = ("acs_url", "sp_metadata_url")


badgr_admin.register(Saml2Configuration, Saml2ConfigurationModelAdmin)


class Saml2AccountModelAdmin(ModelAdmin):
    raw_id_fields = ("user",)
    model = Saml2Account


badgr_admin.register(Saml2Account, Saml2AccountModelAdmin)

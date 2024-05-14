from oauth2_provider.admin import ApplicationAdmin, AccessTokenAdmin
from django.contrib.sites.models import Site
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin
from allauth.socialaccount.admin import SocialApp, SocialAppAdmin, SocialTokenAdmin, SocialAccountAdmin
from allauth.account.admin import EmailAddressAdmin, EmailConfirmationAdmin
from allauth.socialaccount.models import SocialToken, SocialAccount
from django.contrib import messages
from django.contrib.admin import AdminSite, ModelAdmin, StackedInline, TabularInline
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.utils.html import format_html
from django.utils.module_loading import autodiscover_modules
from django.utils.translation import ugettext_lazy
from django_object_actions import DjangoObjectActions
from oauth2_provider.models import get_application_model, get_grant_model, get_access_token_model, \
    get_refresh_token_model

import badgrlog
from badgeuser.models import CachedEmailAddress, ProxyEmailConfirmation
from mainsite.models import BadgrApp, EmailBlacklist, ApplicationInfo, AccessTokenProxy, LegacyTokenProxy, AccessTokenSessionId
from mainsite.utils import backoff_cache_key, set_url_query_params

badgrlogger = badgrlog.BadgrLogger()


class BadgrAdminSite(AdminSite):
    site_header = ugettext_lazy('Badgr')
    index_title = ugettext_lazy('Staff Dashboard')
    site_title = 'Badgr'

    def autodiscover(self):
        autodiscover_modules('admin', register_to=self)

    def login(self, request, extra_context=None):
        response = super(BadgrAdminSite, self).login(request, extra_context)
        if request.method == 'POST':
            # form submission
            if response.status_code != 302:
                # failed /staff login
                username = request.POST.get('username', None)
                badgrlogger.event(badgrlog.FailedLoginAttempt(request, username, endpoint='/staff/login'))

        return response


badgr_admin = BadgrAdminSite(name='badgradmin')

# patch in our delete_selected that calls obj.delete()
# FIXME: custom action broken for django 1.10+
# badgr_admin.disable_action('delete_selected')
# badgr_admin.add_action(delete_selected)


class BadgrAppAdmin(ModelAdmin):
    fieldsets = (
        ('Meta', {'fields': ('is_active', ),
                  'classes': ('collapse',)}),
        (None, {
            'fields': ('name', 'cors', 'oauth_authorization_redirect', 'use_auth_code_exchange', 'oauth_application',
                       'is_default',),
        }),
        ('signup', {
            'fields': ('signup_redirect', 'email_confirmation_redirect', 'forgot_password_redirect',
                       'ui_login_redirect', 'ui_signup_success_redirect', 'ui_signup_failure_redirect',
                       'ui_connect_success_redirect')
        }),
        ('public', {
            'fields': ('public_pages_redirect',)
        })
    )
    list_display = ('name', 'cors',)


badgr_admin.register(BadgrApp, BadgrAppAdmin)


class EmailBlacklistAdmin(ModelAdmin):
    readonly_fields = ('email',)
    list_display = ('email',)
    search_fields = ('email',)


badgr_admin.register(EmailBlacklist, EmailBlacklistAdmin)

# 3rd party apps


class LegacyTokenAdmin(ModelAdmin):
    list_display = ('obscured_token', 'user', 'created')
    list_filter = ('created',)
    raw_id_fields = ('user',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('obscured_token', 'created')
    fields = ('obscured_token', 'user', 'created')

class SiteAdmin(ModelAdmin):
    fields = ('id', 'name', 'domain')
    readonly_fields = ('id',)
    list_display = ('id', 'name', 'domain')
    list_display_links = ('name',)
    search_fields = ('name', 'domain')


badgr_admin.register(LegacyTokenProxy, LegacyTokenAdmin)


badgr_admin.register(SocialApp, SocialAppAdmin)
badgr_admin.register(SocialToken, SocialTokenAdmin)
badgr_admin.register(SocialAccount, SocialAccountAdmin)

badgr_admin.register(Site, SiteAdmin)
badgr_admin.register(Group, GroupAdmin)

badgr_admin.register(CachedEmailAddress, EmailAddressAdmin)
badgr_admin.register(ProxyEmailConfirmation, EmailConfirmationAdmin)


Application = get_application_model()
Grant = get_grant_model()
AccessToken = get_access_token_model()
RefreshToken = get_refresh_token_model()


class ApplicationInfoInline(StackedInline):
    model = ApplicationInfo
    extra = 1
    fieldsets = (
        ('Service Info', {'fields': ('name', 'icon', 'website_url', 'terms_uri', 'policy_uri', 'software_id',
                                     'software_version', 'default_launch_url')}),
        ('Configuration', {'fields': ('allowed_scopes', 'trust_email_verification', 'issue_refresh_token')}),
    )
    readonly_fields = ('default_launch_url',)


class ApplicationInfoAdmin(DjangoObjectActions, ApplicationAdmin):
    fieldsets = (
        (None, {'fields': ('name', 'client_id', 'client_secret', 'client_type', 'authorization_grant_type', 'user',
                           'redirect_uris',)}),
        ('Permissions', {'fields': ('skip_authorization', 'login_backoff',)}),
    )
    readonly_fields = ('login_backoff',)
    inlines = [
        ApplicationInfoInline
    ]
    change_actions = ['launch', 'clear_login_backoff']

    def launch(self, request, obj):
        if obj.authorization_grant_type != Application.GRANT_AUTHORIZATION_CODE:
            messages.add_message(request, messages.INFO, "This is not a Auth Code Application. Cannot Launch.")
            return
        launch_url = BadgrApp.objects.get_current().get_path('/auth/oauth2/authorize')
        launch_url = set_url_query_params(
            launch_url, client_id=obj.client_id, redirect_uri=obj.default_redirect_uri,
            scope=obj.applicationinfo.allowed_scopes
        )
        return HttpResponseRedirect(launch_url)

    def clear_login_backoff(self, request, obj):
        cache_key = backoff_cache_key(obj.client_id)
        cache.delete(cache_key)
    clear_login_backoff.label = "Clear login backoffs"
    clear_login_backoff.short_description = "Remove blocks created by failed login attempts"

    def login_backoff(self, obj):
        cache_key = backoff_cache_key(obj.client_id)
        backoff = cache.get(cache_key)
        if backoff is not None:
            backoff_data = "</li><li>".join(["{ip}: {until} ({count} attempts)".format(
                ip=key,
                until=backoff[key].get('until').astimezone(
                    timezone.get_current_timezone()).strftime("%Y-%m-%d %H:%M:%S"),
                count=backoff[key].get('count')
            ) for key in backoff.keys()])
            return format_html("<ul><li>{}</li></ul>".format(backoff_data))
        return "None"
    login_backoff.allow_tags = True


badgr_admin.register(Application, ApplicationInfoAdmin)
# badgr_admin.register(Grant, GrantAdmin)
# badgr_admin.register(RefreshToken, RefreshTokenAdmin)


class SecuredRefreshTokenInline(TabularInline):
    fields = ('obscured_token', 'user', 'revoked',)
    raw_id_fields = ('user', 'application',)
    readonly_fields = ('user', 'application', 'revoked', 'obscured_token',)
    model = RefreshToken
    extra = 0

    def obscured_token(self, obj):
        if obj.token:
            return "{}***".format(obj.token[:4])
    obscured_token.allow_tags = True

class SecuredAccessTokenSessionIdInline(TabularInline):
    fields = ('obscured_token', 'sessionId',)
    raw_id_fields = ('token',)
    readonly_fields = ('obscured_token', 'sessionId',)
    model = AccessTokenSessionId
    extra = 0

    def obscured_token(self, obj):
        if obj.token:
            return "{}***".format(obj.token.token[:4])
    obscured_token.allow_tags = True


class SecuredAccessTokenAdmin(AccessTokenAdmin):
    list_display = ("obscured_token", "user", "application", "expires")
    raw_id_fields = ('user', 'application')
    fields = ('obscured_token', 'user', 'application', 'expires', 'scope',)
    readonly_fields = ('obscured_token',)
    inlines = [
        SecuredRefreshTokenInline, SecuredAccessTokenSessionIdInline
    ]


badgr_admin.register(AccessTokenProxy, SecuredAccessTokenAdmin)

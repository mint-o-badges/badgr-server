from django.contrib.admin import ModelAdmin, StackedInline, TabularInline
from django.urls import reverse
from django.http import HttpResponseRedirect

from django_object_actions import DjangoObjectActions
from django.utils.safestring import mark_safe

from mainsite.admin import badgr_admin

from .models import Issuer, BadgeClass, BadgeInstance, BadgeInstanceEvidence, BadgeClassAlignment, BadgeClassTag, \
    BadgeClassExtension, IssuerExtension, BadgeInstanceExtension, SuperBadge
from .tasks import resend_notifications


class SuperBadgeInstanceInline(TabularInline):
    model = SuperBadge.assertions.through
    extra = 0
    # raw_id_fields = ('badgeinstance',)

class SuperBadgeAdmin(ModelAdmin):
    # list_display = ('name', 'entity_id', )
    # search_fields = ('name', 'entity_id')
    # fieldsets = (
    #     (None, {'fields': ('created_by', 'name', 'entity_id', 'description', 'share_hash')}),
    # )
    readonly_fields = ('entity_id', )
    inlines = [
        SuperBadgeInstanceInline,
    ]
    pass


class IssuerStaffInline(TabularInline):
    model = Issuer.staff.through
    extra = 0
    raw_id_fields = ('user',)


class IssuerExtensionInline(TabularInline):
    model = IssuerExtension
    extra = 0
    fields = ('name', 'original_json')


class IssuerAdmin(DjangoObjectActions, ModelAdmin):
    readonly_fields = ('created_by', 'created_at', 'updated_at', 'old_json',
                       'source', 'source_url', 'entity_id', 'slug')
    list_display = ('img', 'name', 'entity_id', 'created_by', 'created_at')
    list_display_links = ('img', 'name')
    list_filter = ('created_at',)
    search_fields = ('name', 'entity_id')
    fieldsets = (
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'source', 'source_url', 'entity_id', 'slug'),
            'classes': ("collapse",)
        }),
        (None, {
            'fields': (
                'image', 'name', 'url', 'email', 'verified', 'description', 'category',
                'street', 'streetnumber', 'zip', 'city', 'badgrapp', 'lat', 'lon')
        }),
        ('JSON', {
            'fields': ('old_json',)
        }),
    )
    inlines = [
        IssuerStaffInline,
        IssuerExtensionInline
    ]
    change_actions = ['redirect_badgeclasses']

    def save_model(self, request, obj, form, change):
        force_resize = False
        if 'image' in form.changed_data:
            force_resize = True
        obj.save(force_resize=force_resize)

    def img(self, obj):
        try:
            return mark_safe('<img src="{}" width="32"/>'.format(obj.image.url))
        except ValueError:
            return obj.image
    img.short_description = 'Image'
    img.allow_tags = True

    def redirect_badgeclasses(self, request, obj):
        return HttpResponseRedirect(
            reverse('admin:issuer_badgeclass_changelist') + '?issuer__id={}'.format(obj.id)
        )
    redirect_badgeclasses.label = "BadgeClasses"
    redirect_badgeclasses.short_description = "See this issuer's defined BadgeClasses"


badgr_admin.register(Issuer, IssuerAdmin)
badgr_admin.register(SuperBadge, SuperBadgeAdmin)


class BadgeClassAlignmentInline(TabularInline):
    model = BadgeClassAlignment
    extra = 0
    fields = ('target_name', 'target_url', 'target_description', 'target_framework', 'target_code')


class BadgeClassTagInline(TabularInline):
    model = BadgeClassTag
    extra = 0
    fields = ('name',)


class BadgeClassExtensionInline(TabularInline):
    model = BadgeClassExtension
    extra = 0
    fields = ('name', 'original_json')


class BadgeClassAdmin(DjangoObjectActions, ModelAdmin):
    readonly_fields = ('created_by', 'created_at', 'updated_at', 'old_json',
                       'source', 'source_url', 'entity_id', 'slug')
    list_display = ('badge_image', 'name', 'entity_id', 'issuer_link')
    list_display_links = ('badge_image', 'name',)
    list_filter = ('created_at',)
    search_fields = ('name', 'entity_id', 'issuer__name',)
    raw_id_fields = ('issuer',)
    fieldsets = (
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'source', 'source_url', 'entity_id', 'slug'),
            'classes': ("collapse",)
        }),
        (None, {
            'fields': ('issuer', 'image', 'name', 'description')
        }),
        ('Configuration', {
            'fields': ('criteria_url', 'criteria_text', 'expires_duration', 'expires_amount',)
        }),
        ('JSON', {
            'fields': ('old_json',)
        }),
    )
    inlines = [
        BadgeClassTagInline,
        BadgeClassAlignmentInline,
        BadgeClassExtensionInline,
    ]
    change_actions = ['redirect_issuer', 'redirect_instances']

    def save_model(self, request, obj, form, change):
        force_resize = False
        if 'image' in form.changed_data:
            force_resize = True
        obj.save(force_resize=force_resize)

    def badge_image(self, obj):
        return mark_safe('<img src="{}" width="32"/>'.format(obj.image.url)) if obj.image else ''
    badge_image.short_description = 'Badge'
    badge_image.allow_tags = True

    def issuer_link(self, obj):
        return mark_safe('<a href="{}">{}</a>'.format(reverse("admin:issuer_issuer_change",
            args=(obj.issuer.id,)), obj.issuer.name))
    issuer_link.allow_tags = True

    def redirect_instances(self, request, obj):
        return HttpResponseRedirect(
            reverse('admin:issuer_badgeinstance_changelist') + '?badgeclass__id={}'.format(obj.id)
        )
    redirect_instances.label = "Instances"
    redirect_instances.short_description = "See awarded instances of this BadgeClass"

    def redirect_issuer(self, request, obj):
        return HttpResponseRedirect(
            reverse('admin:issuer_issuer_change', args=(obj.issuer.id,))
        )
    redirect_issuer.label = "Issuer"
    redirect_issuer.short_description = "See this Issuer"


badgr_admin.register(BadgeClass, BadgeClassAdmin)


class BadgeEvidenceInline(StackedInline):
    model = BadgeInstanceEvidence
    fields = ('evidence_url', 'narrative',)
    extra = 0


class BadgeInstanceExtensionInline(TabularInline):
    model = BadgeInstanceExtension
    extra = 0
    fields = ('name', 'original_json')


class BadgeInstanceAdmin(DjangoObjectActions, ModelAdmin):
    readonly_fields = ('created_at', 'created_by', 'updated_at', 'image', 'entity_id',
                       'old_json', 'salt', 'entity_id', 'slug', 'source', 'source_url')
    list_display = ('badge_image', 'recipient_identifier', 'entity_id', 'badgeclass', 'issuer')
    list_display_links = ('badge_image', 'recipient_identifier', )
    list_filter = ('created_at',)
    search_fields = ('recipient_identifier', 'entity_id', 'badgeclass__name', 'issuer__name')
    raw_id_fields = ('badgeclass', 'issuer')
    fieldsets = (
        ('Metadata', {
            'fields': ('source', 'source_url', 'created_by', 'created_at', 'updated_at', 'slug', 'salt'),
            'classes': ("collapse",)
        }),
        ('Badgeclass', {
            'fields': ('badgeclass', 'issuer')
        }),
        ('Assertion', {
            'fields': (
                'entity_id', 'acceptance', 'recipient_type', 'recipient_identifier',
                'image', 'issued_on', 'expires_at', 'narrative')
        }),
        ('Revocation', {
            'fields': ('revoked', 'revocation_reason')
        }),
        ('JSON', {
            'fields': ('old_json',)
        }),
    )
    actions = ['rebake', 'resend_notifications']
    change_actions = ['redirect_issuer', 'redirect_badgeclass']
    inlines = [
        BadgeEvidenceInline,
        BadgeInstanceExtensionInline
    ]

    def rebake(self, request, queryset):
        for obj in queryset:
            obj.rebake(save=True)
    rebake.short_description = "Rebake selected badge instances"

    def badge_image(self, obj):
        try:
            return mark_safe('<img src="{}" width="32"/>'.format(obj.image.url))
        except ValueError:
            return obj.image
    badge_image.short_description = 'Badge'
    badge_image.allow_tags = True

    def has_add_permission(self, request):
        return False

    def redirect_badgeclass(self, request, obj):
        return HttpResponseRedirect(
            reverse('admin:issuer_badgeclass_change', args=(obj.badgeclass.id,))
        )
    redirect_badgeclass.label = "BadgeClass"
    redirect_badgeclass.short_description = "See this BadgeClass"

    def redirect_issuer(self, request, obj):
        return HttpResponseRedirect(
            reverse('admin:issuer_issuer_change', args=(obj.issuer.id,))
        )
    redirect_issuer.label = "Issuer"
    redirect_issuer.short_description = "See this Issuer"

    def resend_notifications(self, request, queryset):
        ids_dict = queryset.only('entity_id').values()
        ids = [i['entity_id'] for i in ids_dict]
        resend_notifications.delay(ids)

    def save_model(self, request, obj, form, change):
        obj.rebake(save=False)
        super().save_model(request, obj, form, change)


badgr_admin.register(BadgeInstance, BadgeInstanceAdmin)


class ExtensionAdmin(ModelAdmin):
    list_display = ('name',)
    search_fields = ('name', 'original_json')


badgr_admin.register(IssuerExtension, ExtensionAdmin)
badgr_admin.register(BadgeClassExtension, ExtensionAdmin)
badgr_admin.register(BadgeInstanceExtension, ExtensionAdmin)

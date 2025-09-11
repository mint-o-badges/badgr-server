from django.db import models
from django.contrib.admin import ModelAdmin, StackedInline, TabularInline
from django.urls import reverse
from django.http import HttpResponseRedirect

from django_object_actions import DjangoObjectActions
from django.utils.safestring import mark_safe
from django import forms

from mainsite.admin import badgr_admin

from .models import (
    ImportedBadgeAssertionExtension,
    Issuer,
    BadgeClass,
    BadgeInstance,
    BadgeInstanceEvidence,
    BadgeClassAlignment,
    BadgeClassTag,
    BadgeClassExtension,
    IssuerExtension,
    BadgeInstanceExtension,
    LearningPath,
    LearningPathBadge,
    LearningPathTag,
    Network,
    NetworkInvite,
    RequestedBadge,
    QrCode,
    RequestedLearningPath,
    IssuerStaffRequest,
    ImportedBadgeAssertion,
)
from .tasks import resend_notifications


class ReadOnlyInline(TabularInline):
    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return list(super().get_fields(request, obj))


class IssuerStaffInline(TabularInline):
    model = Issuer.staff.through
    extra = 0
    raw_id_fields = ("user",)


class IssuerNetworks(ReadOnlyInline):
    model = Network.partner_issuers.through
    extra = 0
    fields = ("network",)


class IssuerExtensionInline(TabularInline):
    model = IssuerExtension
    extra = 0
    fields = ("name", "original_json")


class IssuerBadgeclasses(ReadOnlyInline):
    model = BadgeClass
    extra = 0
    fields = ("name", "assertion_count", "qrcode_count")

    def get_queryset(self, request):
        qs = super(IssuerBadgeclasses, self).get_queryset(request)
        qs = qs.annotate(
            number_of_assertions=models.Count(
                "badgeinstances", filter=models.Q(badgeinstances__revoked=False),
                distinct=True
            )
        )
        qs = qs.annotate(number_of_qrcodes=models.Count("qrcodes", distinct=True))
        return qs

    def assertion_count(self, obj):
        return obj.number_of_assertions

    def qrcode_count(self, obj):
        return obj.number_of_qrcodes


class IssuerAdmin(DjangoObjectActions, ModelAdmin):
    readonly_fields = (
        "created_by",
        "created_at",
        "updated_at",
        "old_json",
        "source",
        "source_url",
        "entity_id",
        "slug",
    )
    list_display = ("img", "name", "created_by", "created_at", "badge_count", "zip")
    list_display_links = ("img", "name")
    list_filter = ("created_at",)
    search_fields = ("name", "entity_id")
    fieldsets = (
        (
            "Metadata",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                    "source",
                    "source_url",
                    "entity_id",
                    "slug",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            None,
            {
                "fields": (
                    "image",
                    "name",
                    "url",
                    "email",
                    "verified",
                    "intendedUseVerified",
                    "description",
                    "category",
                    "street",
                    "streetnumber",
                    "zip",
                    "city",
                    "badgrapp",
                    "lat",
                    "lon",
                )
            },
        ),
        ("JSON", {"fields": ("old_json",)}),
    )
    inlines = [
        IssuerStaffInline,
        IssuerExtensionInline,
        IssuerBadgeclasses,
        IssuerNetworks,
    ]
    change_actions = ["redirect_badgeclasses"]

    def get_queryset(self, request):
        qs = super(IssuerAdmin, self).get_queryset(request)
        qs = qs.annotate(number_of_badges=models.Count("badgeclasses"))
        return qs

    def save_model(self, request, obj, form, change):
        force_resize = False
        if "image" in form.changed_data:
            force_resize = True
        obj.save(force_resize=force_resize)

    def img(self, obj):
        try:
            return mark_safe('<img src="{}" width="32"/>'.format(obj.image.url))
        except ValueError:
            return obj.image

    img.short_description = "Image"
    img.allow_tags = True

    def badge_count(self, obj):
        return obj.number_of_badges

    badge_count.admin_order_field = "number_of_badges"

    def redirect_badgeclasses(self, request, obj):
        return HttpResponseRedirect(
            reverse("admin:issuer_badgeclass_changelist")
            + "?issuer__id={}".format(obj.id)
        )

    redirect_badgeclasses.label = "BadgeClasses"
    redirect_badgeclasses.short_description = "See this issuer's defined BadgeClasses"


badgr_admin.register(Issuer, IssuerAdmin)


class NetworkStaffInline(TabularInline):
    model = Network.staff.through
    extra = 0
    raw_id_fields = ("user",)


class NetworkPartnerIssuers(ReadOnlyInline):
    model = Network.partner_issuers.through
    extra = 0
    fields = ("issuer",)


class NetworkAdmin(DjangoObjectActions, ModelAdmin):
    readonly_fields = (
        "created_by",
        "created_at",
        "updated_at",
        "source",
        "source_url",
        "entity_id",
        "slug",
    )
    list_display = ("img", "name", "created_by", "created_at")
    list_display_links = ("img", "name")
    list_filter = ("created_at",)
    search_fields = ("name", "entity_id")
    fieldsets = (
        (
            "Metadata",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                    "source",
                    "source_url",
                    "entity_id",
                    "slug",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            None,
            {
                "fields": (
                    "image",
                    "name",
                    "url",
                    "description",
                    "badgrapp",
                    "country",
                    "state",
                )
            },
        ),
    )
    inlines = [NetworkStaffInline, NetworkPartnerIssuers]

    def save_model(self, request, obj, form, change):
        force_resize = False
        if "image" in form.changed_data:
            force_resize = True
        obj.save(force_resize=force_resize)

    def img(self, obj):
        try:
            return mark_safe('<img src="{}" width="32"/>'.format(obj.image.url))
        except ValueError:
            return obj.image

    img.short_description = "Image"
    img.allow_tags = True


badgr_admin.register(Network, NetworkAdmin)


class BadgeClassAlignmentInline(TabularInline):
    model = BadgeClassAlignment
    extra = 0
    fields = (
        "target_name",
        "target_url",
        "target_description",
        "target_framework",
        "target_code",
    )


class BadgeClassTagInline(TabularInline):
    model = BadgeClassTag
    extra = 0
    fields = ("name",)


class BadgeClassExtensionInline(TabularInline):
    model = BadgeClassExtension
    extra = 0
    fields = ("name", "original_json")


class BinaryMultipleChoiceField(forms.MultipleChoiceField):
    widget = forms.CheckboxSelectMultiple

    def to_python(self, value):
        if not value:
            return 0
        else:
            return sum(map(int, value))

    def prepare_value(self, value):
        binary = bin(value)[:1:-1]
        ret = [pow(int(x) * 2, i) for i, x in enumerate(binary) if int(x)]
        return ret

    def validate(self, value):
        return isinstance(value, int)

    def has_changed(self, initial, data):
        return initial != data


class BadgeModelForm(forms.ModelForm):
    copy_permissions = BinaryMultipleChoiceField(
        required=False,
        choices=BadgeClass.COPY_PERMISSIONS_CHOICES,
    )

    class Meta:
        exclude = []
        model = BadgeClass


class BadgeClassAdmin(DjangoObjectActions, ModelAdmin):
    form = BadgeModelForm

    readonly_fields = (
        "created_by",
        "created_at",
        "updated_at",
        "old_json",
        "source",
        "source_url",
        "entity_id",
        "slug",
        "criteria",
    )
    list_display = ("badge_image", "name", "issuer_link", "assertion_count")
    list_display_links = (
        "badge_image",
        "name",
    )
    list_filter = ("created_at",)
    search_fields = (
        "name",
        "entity_id",
        "issuer__name",
    )
    raw_id_fields = ("issuer",)
    fieldsets = (
        (
            "Metadata",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                    "source",
                    "source_url",
                    "entity_id",
                    "slug",
                ),
                "classes": ("collapse",),
            },
        ),
        (None, {"fields": ("issuer", "image", "imageFrame", "name", "description")}),
        (
            "Configuration",
            {
                "fields": (
                    "criteria_url",
                    "criteria_text",
                    "expires_duration",
                    "expires_amount",
                    "copy_permissions",
                )
            },
        ),
        ("JSON", {"fields": ("old_json", "criteria")}),
    )
    inlines = [
        BadgeClassTagInline,
        BadgeClassAlignmentInline,
        BadgeClassExtensionInline,
    ]
    change_actions = ["redirect_issuer", "redirect_instances"]

    def get_queryset(self, request):
        qs = super(BadgeClassAdmin, self).get_queryset(request)
        qs = qs.annotate(
            number_of_assertions=models.Count(
                "badgeinstances", filter=models.Q(badgeinstances__revoked=False)
            )
        )
        return qs

    def save_model(self, request, obj, form, change):
        force_resize = False
        if "image" in form.changed_data:
            force_resize = True
        obj.save(force_resize=force_resize)

    def badge_image(self, obj):
        return (
            mark_safe('<img src="{}" width="32"/>'.format(obj.image.url))
            if obj.image
            else ""
        )

    badge_image.short_description = "Badge"
    badge_image.allow_tags = True

    def issuer_link(self, obj):
        return mark_safe(
            '<a href="{}">{}</a>'.format(
                reverse("admin:issuer_issuer_change", args=(obj.issuer.id,)),
                obj.issuer.name,
            )
        )

    issuer_link.allow_tags = True
    issuer_link.admin_order_field = "issuer"

    def redirect_instances(self, request, obj):
        return HttpResponseRedirect(
            reverse("admin:issuer_badgeinstance_changelist")
            + "?badgeclass__id={}".format(obj.id)
        )

    redirect_instances.label = "Instances"
    redirect_instances.short_description = "See awarded instances of this BadgeClass"

    def redirect_issuer(self, request, obj):
        return HttpResponseRedirect(
            reverse("admin:issuer_issuer_change", args=(obj.issuer.id,))
        )

    redirect_issuer.label = "Issuer"
    redirect_issuer.short_description = "See this Issuer"

    def assertion_count(self, obj):
        return obj.number_of_assertions

    assertion_count.admin_order_field = "number_of_assertions"


badgr_admin.register(BadgeClass, BadgeClassAdmin)


class BadgeEvidenceInline(StackedInline):
    model = BadgeInstanceEvidence
    fields = (
        "evidence_url",
        "narrative",
    )
    extra = 0


class BadgeInstanceExtensionInline(TabularInline):
    model = BadgeInstanceExtension
    extra = 0
    fields = ("name", "original_json")


class BadgeInstanceAdmin(DjangoObjectActions, ModelAdmin):
    readonly_fields = (
        "created_at",
        "created_by",
        "updated_at",
        "image",
        "entity_id",
        "old_json",
        "salt",
        "entity_id",
        "slug",
        "source",
        "source_url",
    )
    list_display = (
        "badge_image",
        "recipient_identifier",
        "entity_id",
        "badgeclass",
        "issuer",
    )
    list_display_links = (
        "badge_image",
        "recipient_identifier",
    )
    list_filter = ("created_at",)
    search_fields = (
        "recipient_identifier",
        "entity_id",
        "badgeclass__name",
        "issuer__name",
    )
    raw_id_fields = ("badgeclass", "issuer")
    fieldsets = (
        (
            "Metadata",
            {
                "fields": (
                    "source",
                    "source_url",
                    "created_by",
                    "created_at",
                    "updated_at",
                    "slug",
                    "salt",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Badgeclass", {"fields": ("badgeclass", "issuer")}),
        (
            "Assertion",
            {
                "fields": (
                    "entity_id",
                    "acceptance",
                    "recipient_type",
                    "recipient_identifier",
                    "image",
                    "issued_on",
                    "expires_at",
                    "narrative",
                )
            },
        ),
        ("Revocation", {"fields": ("revoked", "revocation_reason")}),
        ("JSON", {"fields": ("old_json",)}),
    )
    actions = ["rebake", "resend_notifications"]
    change_actions = ["redirect_issuer", "redirect_badgeclass"]
    inlines = [BadgeEvidenceInline, BadgeInstanceExtensionInline]

    def rebake(self, request, queryset):
        for obj in queryset:
            obj.rebake(save=True)

    rebake.short_description = "Rebake selected badge instances"

    def badge_image(self, obj):
        try:
            return mark_safe('<img src="{}" width="32"/>'.format(obj.image.url))
        except ValueError:
            return obj.image

    badge_image.short_description = "Badge"
    badge_image.allow_tags = True

    def has_add_permission(self, request):
        return False

    def redirect_badgeclass(self, request, obj):
        return HttpResponseRedirect(
            reverse("admin:issuer_badgeclass_change", args=(obj.badgeclass.id,))
        )

    redirect_badgeclass.label = "BadgeClass"
    redirect_badgeclass.short_description = "See this BadgeClass"

    def redirect_issuer(self, request, obj):
        return HttpResponseRedirect(
            reverse("admin:issuer_issuer_change", args=(obj.issuer.id,))
        )

    redirect_issuer.label = "Issuer"
    redirect_issuer.short_description = "See this Issuer"

    def resend_notifications(self, request, queryset):
        ids_dict = queryset.only("entity_id").values()
        ids = [i["entity_id"] for i in ids_dict]
        resend_notifications.delay(ids)

    def save_model(self, request, obj, form, change):
        obj.rebake(save=False)
        super().save_model(request, obj, form, change)


badgr_admin.register(BadgeInstance, BadgeInstanceAdmin)


class ImportedBadgeAssertionExtensionInline(TabularInline):
    model = ImportedBadgeAssertionExtension
    extra = 0
    fields = ("name", "original_json")


class ImportedBadgeAssertionAdmin(ModelAdmin):
    readonly_fields = (
        "created_at",
        "created_by",
        "updated_at",
        "entity_id",
        "issuer_image_url",
        "badge_image_url",
    )
    list_display = (
        "recipient_identifier",
        "entity_id",
        "badge_name",
        "badge_description",
    )
    list_display_links = ("recipient_identifier",)
    list_filter = ("created_at",)
    inlines = [ImportedBadgeAssertionExtensionInline]
    fieldsets = (
        (
            "Metadata",
            {
                "fields": (
                    "source",
                    "source_url",
                    "created_by",
                    "created_at",
                    "updated_at",
                    "salt",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Assertion",
            {
                "fields": (
                    "entity_id",
                    "acceptance",
                    "recipient_type",
                    "recipient_identifier",
                    "issued_on",
                    "expires_at",
                    "narrative",
                    "badge_image_url",
                    "issuer_image_url",
                )
            },
        ),
        ("Revocation", {"fields": ("revoked", "revocation_reason")}),
        ("JSON", {"fields": ("original_json",)}),
    )


badgr_admin.register(ImportedBadgeAssertion, ImportedBadgeAssertionAdmin)


class ExtensionAdmin(ModelAdmin):
    list_display = ("name",)
    search_fields = ("name", "original_json")


badgr_admin.register(IssuerExtension, ExtensionAdmin)
badgr_admin.register(BadgeClassExtension, ExtensionAdmin)
badgr_admin.register(BadgeInstanceExtension, ExtensionAdmin)
badgr_admin.register(ImportedBadgeAssertionExtension, ExtensionAdmin)


class ReqeustedBadgeAdmin(ModelAdmin):
    list_display = (
        "firstName",
        "lastName",
        "email",
        "badgeclass",
        "user",
        "requestedOn",
        "status",
    )
    readonly_fields = ("requestedOn", "status")


badgr_admin.register(RequestedBadge, ReqeustedBadgeAdmin)


class IssuerStaffRequestAdmin(ModelAdmin):
    list_display = ("issuer", "user", "requestedOn", "status")
    readonly_fields = ("requestedOn", "status")


badgr_admin.register(IssuerStaffRequest, IssuerStaffRequestAdmin)


class NetworkInviteAdmin(ModelAdmin):
    list_display = ("network", "issuer", "invitedOn", "status")
    readonly_fields = ("invitedOn", "status")


badgr_admin.register(NetworkInvite, NetworkInviteAdmin)


class QrCodeAdmin(ModelAdmin):
    list_display = ("title", "createdBy", "valid_from", "expires_at")


badgr_admin.register(QrCode, QrCodeAdmin)


class ReqeustedLearningPathAdmin(ModelAdmin):
    list_display = ("learningpath", "user", "requestedOn", "status")
    readonly_fields = ("requestedOn", "status")


badgr_admin.register(RequestedLearningPath, ReqeustedLearningPathAdmin)


class LearningPathTagInline(TabularInline):
    model = LearningPathTag
    extra = 0
    fields = ("name",)


class LearningPathBadgeInline(TabularInline):
    model = LearningPathBadge
    extra = 0
    fields = ("badge", "order")


class LearningPathAdmin(ModelAdmin):
    list_display = ("name", "issuer", "required_badges_count")
    search_fields = ("name", "description")
    inlines = [LearningPathTagInline, LearningPathBadgeInline]


badgr_admin.register(LearningPath, LearningPathAdmin)

from django.urls import reverse
from django.conf import settings
from django.http import Http404
from django.views.generic import RedirectView

from django.core.exceptions import PermissionDenied

from backpack.models import BackpackCollection
from issuer.models import BadgeInstance, BadgeClass, Issuer, IssuerStaff
from badgeuser.models import BadgeUser
from mainsite.collection_pdf import CollectionPDFCreator

from rest_framework.decorators import (
    permission_classes,
    authentication_classes,
    api_view,
)

from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, BasicAuthentication, TokenAuthentication
from django.http import HttpResponse
from mainsite.utils import get_name
from mainsite.badge_pdf import BadgePDFCreator


@api_view(["GET"])
@authentication_classes([TokenAuthentication, SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def pdf(request, *args, **kwargs):
    slug = kwargs["slug"]
    try:
        badgeinstance = BadgeInstance.objects.get(entity_id=slug)

        # Get emails of all issuer owners
        """ issuer= Issuer.objects.get(entity_id=badgeinstance.issuer.entity_id)
        issuer_owners = issuer.staff.filter(issuerstaff__role=IssuerStaff.ROLE_OWNER)
        issuer_owners_emails = list(map(attrgetter('primary_email'), issuer_owners)) """

        # User must be the recipient or an issuer staff with OWNER role
        # TODO: Check other recipient types 
        # Temporary commented out
        """ if request.user.email != badgeinstance.recipient_identifier and request.user.email not in issuer_owners_emails:
            raise PermissionDenied """
    except BadgeInstance.DoesNotExist:
        raise Http404
    try:
        badgeclass = BadgeClass.objects.get(
            entity_id=badgeinstance.badgeclass.entity_id
        )
    except BadgeClass.DoesNotExist:
        raise Http404

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="badge.pdf"'

    pdf_creator = BadgePDFCreator()
    pdf_content = pdf_creator.generate_pdf(badgeinstance, badgeclass, origin=request.META.get("HTTP_ORIGIN"))
    return HttpResponse(pdf_content, content_type="application/pdf")

@api_view(["GET"])
@authentication_classes([TokenAuthentication, SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def collectionPdf(request, *args, **kwargs):
    slug = kwargs["slug"]
    try:
        collection = BackpackCollection.objects.get(entity_id=slug)
    except BackpackCollection.DoesNotExist:
        raise Http404
    
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="badge.pdf"'

    pdf_creator = CollectionPDFCreator()
    pdf_content = pdf_creator.generate_pdf(collection, origin=request.META.get("HTTP_ORIGIN"))
    return HttpResponse(pdf_content, content_type="application/pdf")
   



class RedirectSharedCollectionView(RedirectView):
    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        share_hash = kwargs.get("share_hash", None)
        if not share_hash:
            raise Http404

        try:
            collection = BackpackCollection.cached.get_by_slug_or_entity_id_or_id(
                share_hash
            )
        except BackpackCollection.DoesNotExist:
            raise Http404
        return collection.public_url


class LegacyCollectionShareRedirectView(RedirectView):
    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        new_pattern_name = self.request.resolver_match.url_name.replace("legacy_", "")
        kwargs.pop("pk")
        url = reverse(new_pattern_name, args=args, kwargs=kwargs)
        return url


class LegacyBadgeShareRedirectView(RedirectView):
    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        badgeinstance = None
        share_hash = kwargs.get("share_hash", None)
        if not share_hash:
            raise Http404

        try:
            badgeinstance = BadgeInstance.cached.get_by_slug_or_entity_id_or_id(
                share_hash
            )
        except BadgeInstance.DoesNotExist:
            pass

        if not badgeinstance:
            # legacy badge share redirects need to support lookup by pk
            try:
                badgeinstance = BadgeInstance.cached.get(pk=share_hash)
            except (BadgeInstance.DoesNotExist, ValueError):
                pass

        if not badgeinstance:
            raise Http404

        return badgeinstance.public_url

import urllib.request
import urllib.parse
import urllib.error

from django.conf import settings
from django.http import Http404

from issuer.models import BadgeInstance


class ShareProvider(object):
    provider_code = None

    def __init__(self, provider):
        self.provider = provider


class TwitterShareProvider(ShareProvider):
    provider_code = 'twitter'
    provider_name = 'Twitter'

    def share_url(self, obj, **kwargs):
        if isinstance(obj, BadgeInstance):
            text = "I earned a badge from {issuer}! {url}".format(
                issuer=obj.cached_issuer.name,
                url=obj.get_share_url(**kwargs)
            )
        else:
            text = obj.share_url
        return "https://twitter.com/intent/tweet?text={text}".format(
            text=urllib.parse.quote(text)
        )


class FacebookShareProvider(ShareProvider):
    provider_code = 'facebook'
    provider_name = 'Facebook'

    def share_url(self, badge_instance, **kwargs):
        return "https://www.facebook.com/sharer/sharer.php?u={url}".format(
            url=urllib.parse.quote(badge_instance.get_share_url(**kwargs))
        )


class PinterestShareProvider(ShareProvider):
    provider_code = 'pinterest'
    provider_name = 'Pinterest'

    def share_url(self, badge_instance, **kwargs):
        summary = badge_instance.cached_badgeclass.name
        return ("http://www.pinterest.com/pin/create/button/"
                "?url={url}&media={image}&description={summary}".format(
                    url=urllib.parse.quote(badge_instance.get_share_url(**kwargs)),
                    image=badge_instance.image_url(),
                    summary=summary
                    ))


class LinkedinShareProvider(ShareProvider):
    provider_code = 'linkedin'
    provider_name = 'LinkedIn'

    def share_url(self, instance, **kwargs):
        url = None
        # sharing as a certification is broken so disabling for now [Wiggins june 2017]
        # if hasattr(instance, 'cached_badgeclass'):
        #     url = self.certification_share_url(instance, **kwargs)

        if not url and isinstance(instance, BadgeInstance):
            url = self.feed_share_url(instance, **kwargs)
        elif not url:
            return self.collection_share_url(instance, **kwargs)
        return url

    def feed_share_url(self, badge_instance, title=None, summary=None, **kwargs):
        if title is None:
            issuer_name = badge_instance.issuer.name
            title = "I earned a badge from {issuer}!".format(issuer=issuer_name)

        if summary is None:
            summary = badge_instance.cached_badgeclass.name
        return ("https://www.linkedin.com/shareArticle"
                "?mini=true&url={url}&title={title}&summary={summary}".format(
                    url=urllib.parse.quote(badge_instance.get_share_url(**kwargs)),
                    title=urllib.parse.quote(title),
                    summary=urllib.parse.quote(summary),
                    ))

    def collection_share_url(self, collection, **kwargs):
        title = collection.name
        summary = collection.description
        return ("https://www.linkedin.com/shareArticle"
                "?mini=true&url={url}&title={title}&summary={summary}".format(
                    url=urllib.parse.quote(collection.get_share_url(**kwargs)),
                    title=urllib.parse.quote(title),
                    summary=urllib.parse.quote(summary),
                    ))

    def certification_share_url(self, badge_instance, **kwargs):
        cert_issuer_id = getattr(settings, 'LINKEDIN_CERTIFICATION_ISSUER_ID', None)
        if cert_issuer_id is None:
            return None
        return ("https://www.linkedin.com/profile/add"
                "?_ed={certIssuerId}&pfCertificationName={name}&pfCertificationUrl={url}".format(
                    certIssuerId=cert_issuer_id,
                    name=urllib.parse.quote(badge_instance.cached_badgeclass.name),
                    url=urllib.parse.quote(badge_instance.share_url(**kwargs))
                    ))


class SharingManager(object):
    provider_code = None
    ManagerProviders = {
        FacebookShareProvider.provider_code: FacebookShareProvider,
        LinkedinShareProvider.provider_code: LinkedinShareProvider,
        TwitterShareProvider.provider_code: TwitterShareProvider,
        PinterestShareProvider.provider_code: PinterestShareProvider,
    }

    @classmethod
    def share_url(cls, provider, badge_instance, include_identifier=False, **kwargs):
        manager_cls = SharingManager.ManagerProviders.get(provider.lower(), None)
        if manager_cls is None:
            raise Http404(u"Provider not supported: {}".format(provider))
        manager = manager_cls(provider)
        url = manager.share_url(badge_instance, include_identifier=include_identifier)
        return url

    @classmethod
    def is_provider_supported(cls, provider):
        return provider in SharingManager.ManagerProviders

from allauth.socialaccount import providers
from allauth.socialaccount.providers.twitter.provider import TwitterProvider, TwitterAccount


class TwitterProviderWithIdentifier(TwitterProvider):
    id = 'twitter'
    name = 'Twitter'
    package = 'allauth.socialaccount.providers.twitter'
    account_class = TwitterAccount

    def extract_common_fields(self, data):
        common_fields = super(TwitterProviderWithIdentifier, self).extract_common_fields(data)
        common_fields['url'] = 'https://twitter.com/{}'.format(data.get('screen_name'))
        return common_fields


providers.registry.register(TwitterProviderWithIdentifier)

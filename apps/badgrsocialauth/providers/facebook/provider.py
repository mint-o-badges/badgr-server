from allauth.account.models import EmailAddress
from allauth.socialaccount import providers
from allauth.socialaccount.providers.facebook.provider import FacebookProvider, FacebookAccount


class VerifiedFacebookProvider(FacebookProvider):
    id = 'facebook'
    name = 'Facebook'
    package = 'allauth.socialaccount.providers.facebook'
    account_class = FacebookAccount

    def extract_email_addresses(self, data):
        """
        Force verification of email addresses
        """
        ret = []
        email = data.get('email')
        if email and data.get('email'):
            ret.append(EmailAddress(email=email,
                                    verified=True,  # Originally verified=False
                                    primary=True))
        return ret


providers.registry.register(VerifiedFacebookProvider)

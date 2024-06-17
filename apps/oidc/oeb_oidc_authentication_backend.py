import logging
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from mozilla_django_oidc.utils import absolutify

from django.core.exceptions import SuspiciousOperation
from django.urls import reverse

from badgeuser.utils import generate_badgr_username

LOGGER = logging.getLogger(__name__)

# Since we only get the subject identifier from meinBildungsraum,
# we don't necessarily know the E-Mail address of the user.
# Thus we initiate the E-Mail address with <sub>@unknown.unknown.
# This E-Mail address is later also used to generate the username;
# The username is however not updated when the E-Mail address is
# updated.
def convertSubToMail(sub: str) -> str:
    return f'{sub}@unknown.unknown'

def convertSubToUsername(sub: str) -> str:
    mail = convertSubToMail(sub)
    return generate_badgr_username(mail)

class OebOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    def filter_users_by_claims(self, claims):
        sub = claims.get('sub')
        if not sub:
            return self.UserModel.objects.none()

        username = convertSubToUsername(sub)
        return self.UserModel.objects.filter(username=username)

    def create_user(self, claims):
        user = super(OebOIDCAuthenticationBackend, self).create_user(claims)

        user.first_name = 'unknown'
        user.last_name = 'unknown'
        user.email = convertSubToMail(claims.get('sub'))
        user.set_email_items([{
            'primary': True,
            # Set this to verified since this is required for the user to be able to login.
            # Note that this kinda breaches our idea of always having a verified mail;
            # Since the mail actually only is a dummy mail. TODO: Handle this case
            'verified': True,
            'email': user.email,
        }], allow_verify=True)
        if user.username == 'unknown':
            # The username is set to unknown if the email was None
            user.username = convertSubToUsername(claims.get('sub'))
        user.save()

        return user
    
    def update_user(self, user, claims):
        # Don't update based on data from OIDC
        return user

# TODO: I don't understand why I put this here, if it's not
# needed remove the commented code
   # def verify_jws(self, payload, key):
   #     return super(OebOIDCAuthenticationBackend, self).verify_jws(payload, key)
   # 
   # def verify_token(self, token, nonce):
   #     return super(OebOIDCAuthenticationBackend, self).verify_token(token, nonce=nonce)
    
    # Overwrite to prevent warning, since we don't receive the email
    def verify_claims(self, claims):
        scopes = self.get_settings("OIDC_RP_SCOPES", "openid")
        if "openid" in scopes.split():
            return "sub" in claims
        return super().verify_claims(claims)


    def authenticate(self, request, **kwargs):
        """Authenticates a user based on the OIDC code flow.

        This is copied from [here](https://dev.to/hesbon/customizing-mozilla-django-oidc-544p),
        which in turn is *almost* an exact copy of the original code,
        except for the addition of the refresh token.
        """

        self.request = request
        if not self.request:
            return None

        state = self.request.GET.get("state")
        code = self.request.GET.get("code")
        nonce = kwargs.pop("nonce", None)
        code_verifier = kwargs.pop("code_verifier", None)

        if not code or not state:
            return None

        reverse_url = self.get_settings(
            "OIDC_AUTHENTICATION_CALLBACK_URL", "oidc_authentication_callback"
        )

        token_payload = {
            "client_id": self.OIDC_RP_CLIENT_ID,
            "client_secret": self.OIDC_RP_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": absolutify(self.request, reverse(reverse_url)),
        }

        # Send code_verifier with token request if using PKCE
        if code_verifier is not None:
            token_payload.update({"code_verifier": code_verifier})

        # Get the token
        token_info = self.get_token(token_payload)
        id_token = token_info.get("id_token")
        access_token = token_info.get("access_token")
        # In addition we also get the refresh token
        refresh_token = token_info.get("refresh_token")

        # Validate the token
        payload = self.verify_token(id_token, nonce=nonce)

        if payload:
            self.store_tokens(access_token, id_token, refresh_token)
            try:
                return self.get_or_create_user(access_token, id_token, payload)
            except SuspiciousOperation as exc:
                LOGGER.warning("failed to get or create user: %s", exc)
                return None

        return None

    def store_tokens(self, access_token, id_token, refresh_token):
        # Differently to the [tutorial](https://dev.to/hesbon/customizing-mozilla-django-oidc-544p)
        # I call the super method here, to reduce the duplicate code
        super(OebOIDCAuthenticationBackend, self).store_tokens(access_token, id_token)

        session = self.request.session
        if self.get_settings("OIDC_STORE_REFRESH_TOKEN", True):
            session["oidc_refresh_token"] = refresh_token




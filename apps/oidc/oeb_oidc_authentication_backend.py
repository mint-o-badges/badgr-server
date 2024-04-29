from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from badgeuser.utils import generate_badgr_username

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
        if user.username == 'unknown':
            # The username is set to unknown if the email was None
            user.username = convertSubToUsername(claims.get('sub'))
        user.save()

        return user

    def update_user(self, user, claims):
        # Don't update based on data from OIDC
        return user

    def verify_jws(self, payload, key):
        return super(OebOIDCAuthenticationBackend, self).verify_jws(payload, key)
    
    def verify_token(self, token, nonce):
        return super(OebOIDCAuthenticationBackend, self).verify_token(token, nonce=nonce)

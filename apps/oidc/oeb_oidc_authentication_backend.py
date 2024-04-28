from mozilla_django_oidc.auth import OIDCAuthenticationBackend

class OebOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    def filter_users_by_claims(self, claims):
        return self.UserModel.objects.none()

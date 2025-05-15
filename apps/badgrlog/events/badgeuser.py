from mainsite.utils import client_ip_from_request

from .base import BaseBadgrEvent


class UserSignedUp(BaseBadgrEvent):

    def __init__(self, request, user, **kwargs):
        self.request = request
        self.user = user

    def to_representation(self):
        return {
            "username": self.user.username,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "email": self.user.email,
        }


class EmailConfirmed(BaseBadgrEvent):

    def __init__(self, request, email_address, **kwargs):
        self.request = request
        self.email_address = email_address

    def to_representation(self):
        return {
            "email": self.email_address.email,
        }


class FailedLoginAttempt(BaseBadgrEvent):
    def __init__(self, request, username, endpoint, **kwargs):
        self.request = request
        self.username = username
        self.endpoint = endpoint

    def to_representation(self):
        return {
            "username": self.username,
            "endpoint": self.endpoint,
            "ipAddress": client_ip_from_request(self.request),
        }


class DeprecatedApiAuthToken(BaseBadgrEvent):
    def __init__(self, request, username, **kwargs):
        self.request = request
        self.username = username
        self.is_new_token = kwargs.get("is_new_token", False)

    def to_representation(self):
        return {
            "username": self.username,
            "ipAddress": client_ip_from_request(self.request),
            "newToken": self.is_new_token,
        }


class NoBadgrApp(BaseBadgrEvent):

    def __init__(self, request, badgrapp_id, **kwargs):
        self.request = request
        self.badgrapp_id = badgrapp_id

    def to_representation(self):
        return {
            "badgrapp_id": self.badgrapp_id,
        }


class NoEmailConfirmation(BaseBadgrEvent):

    def to_representation(self):
        return {}


class NoEmailConfirmationEmailAddress(BaseBadgrEvent):

    def __init__(self, request, email_address, **kwargs):
        self.request = request
        self.email_address = email_address

    def to_representation(self):
        return {
            "email": self.email_address.email,
        }


class InvalidEmailConfirmationToken(BaseBadgrEvent):

    def __init__(self, request, email_address, token, **kwargs):
        self.request = request
        self.email_address = email_address
        self.token = token

    def to_representation(self):
        return {
            "email": self.email_address.email,
            "token": self.token,
        }


class EmailConfirmationTokenExpired(BaseBadgrEvent):

    def __init__(self, request, email_address, **kwargs):
        self.request = request
        self.email_address = email_address

    def to_representation(self):
        return {
            "email": self.email_address.email,
        }


class OtherUsersEmailConfirmationToken(BaseBadgrEvent):

    def __init__(self, request, email_address, other_user, token, **kwargs):
        self.request = request
        self.email_address = email_address
        self.other_user = other_user
        self.token = token

    def to_representation(self):
        return {
            "email": self.email_address.email,
            "other_user_email": self.other_user.email,
            "token": self.token,
        }


class EmailConfirmationAlreadyVerified(BaseBadgrEvent):

    def __init__(self, request, email_address, token, **kwargs):
        self.request = request
        self.email_address = email_address
        self.token = token

    def to_representation(self):
        return {
            "email": self.email_address.email,
            "token": self.token,
        }

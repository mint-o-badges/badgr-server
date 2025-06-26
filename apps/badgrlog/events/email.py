from .base import BaseBadgrEvent


class EmailRendered(BaseBadgrEvent):
    def __init__(self, email):
        self.email = email

    def to_representation(self):
        return {
            "subject": self.email.subject,
            "fromAddress": self.email.from_email,
            "toAddress": self.email.to,
        }

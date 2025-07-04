import datetime

from .base import BaseBadgrEvent


class BadgeSharedEvent(BaseBadgrEvent):
    def __init__(self, assertion, platform, shared_date, source):
        if not isinstance(shared_date, datetime.datetime):
            raise ValueError("shared_date parameter must be a datetime object")

        self.issuer_ob_id = assertion.issuer_jsonld_id
        self.badgeclass_ob_id = assertion.badgeclass_jsonld_id
        self.assertion_ob_id = assertion.jsonld_id
        self.recipient_identifier = assertion.recipient_identifier
        self.recipient_type = assertion.recipient_type
        self.platform = platform
        self.shared_date = shared_date
        self.source = source

    def to_representation(self):
        return {
            "issuer_ob_id": self.issuer_ob_id,
            "badgeclass_ob_id": self.badgeclass_ob_id,
            "assertion_ob_id": self.assertion_ob_id,
            "recipient": {
                "value": self.recipient_identifier,
                "type": self.recipient_type,
            },
            "platform": self.platform,
            "shared_date": self.serializeWithUTCWithZ(self.shared_date),
            "source": self.source,
        }

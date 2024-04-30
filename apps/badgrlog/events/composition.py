# Created by wiggins@concentricsky.com on 9/10/15.
from .base import BaseBadgrEvent


class BadgeUploaded(BaseBadgrEvent):
    def __init__(self, instance):
        self.instance = instance

    def to_representation(self):
        user_id = ""
        if (
            self.instance.recipient_user is not None
            and self.instance.recipient_user.entity_id is not None
        ):
            user_id = self.instance.recipient_user.entity_id
        return {"user_entityId": user_id, "badgeInstance": self.instance}


class InvalidBadgeUploadReport:
    def __init__(
        self, image_data="", user_entity_id="", error_name="", error_result=""
    ):
        self.image_data = image_data
        self.user_entity_id = user_entity_id
        self.error_name = error_name
        self.error_result = error_result


class InvalidBadgeUploaded(BaseBadgrEvent):

    def __init__(self, error_report):
        self.error_report = error_report

    def to_representation(self):
        return {
            "userId": self.error_report.user_entity_id,
            "imageData": self.error_report.image_data,
            "errorName": self.error_report.error_name,
            "errorMessage": self.error_report.error_result,
        }

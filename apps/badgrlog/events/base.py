# Created by wiggins@concentricsky.com on 8/27/15.
import datetime
import uuid

import django.utils.timezone as timezone
import pytz


class BaseBadgrEvent(object):
    def serializeWithUTCWithZ(self, date):
        if timezone.is_aware(date):
            tz_datetime = date.astimezone(pytz.utc)
        else:
            tz_datetime = timezone.make_aware(date, pytz.utc)
        tz_datetime = tz_datetime.isoformat()
        if tz_datetime.endswith("+00:00"):
            tz_datetime = tz_datetime[:-6] + "Z"
        return tz_datetime

    def get_type(self):
        return self.__class__.__name__

    def to_representation(self):
        raise NotImplementedError("subclasses must provide a to_representation method")

    def compacted(self):
        data = self.to_representation()
        data.update(
            {
                "type": "Action",
                "actionType": self.get_type(),
                "timestamp": self.serializeWithUTCWithZ(datetime.datetime.now()),
                "event_id": str(uuid.uuid4()),
            }
        )
        return data

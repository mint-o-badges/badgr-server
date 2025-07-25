import datetime

from django.core.management.base import BaseCommand

import logging
logger = logging.getLogger("Badgr.Events")

from backpack.models import BackpackBadgeShare


class Command(BaseCommand):
    def handle(self, *args, **options):
        logger.info("Start emit old share events to badgr events log at %s",
                    datetime.datetime.now())

        chunk_size = 5000
        start_index = 0
        processing_index = 1

        while True:
            start = start_index
            end = start_index + chunk_size

            shares = BackpackBadgeShare.objects.order_by("id")[start:end]
            for share in shares:
                self.stdout.write("Processing shares %s" % processing_index)
                logger.info("Badge '%s' shared by '%s' at '%s' from '%s'",
                            share.badgeinstance.entity_id, share.provider, share.created_at, share.source)
                processing_index = processing_index + 1
            if len(shares) < chunk_size:
                break
            start_index += chunk_size

        self.stdout.write(
            "End emit old share events to badgr events log at %s"
            % datetime.datetime.now()
        )

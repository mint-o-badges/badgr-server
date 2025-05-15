# encoding: utf-8
from django.core.management import BaseCommand
from issuer.models import BadgeClass


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            help="Number of model instances to process in a batch",
            default=1000,
        )

    def handle(self, *args, **options):
        model = BadgeClass
        processed_count = 0
        limit = options["limit"]
        queryset = model.objects.filter(image_hash="").exclude(image="")

        processing = True
        while processing:
            active_set = queryset[0:limit]
            self.stdout.write(str(active_set.query))
            if active_set.exists():
                for instance in active_set:
                    instance.save()
                    self.stdout.write(
                        "Calculated initial image_hash for {} #{}: {}".format(
                            instance.__class__.__name__,
                            instance.pk,
                            instance.image_hash,
                        )
                    )
                    processed_count += 1

            else:
                processing = False

        self.stdout.write(
            "Finished processing populate_image_hashes for model {}. {} records updated.".format(
                model.__name__, processed_count
            )
        )

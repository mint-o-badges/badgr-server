from django.core.management.base import BaseCommand
from django.db import models
from geopy.geocoders import Nominatim
import time
from issuer.models import Issuer


class Command(BaseCommand):
    help = "Geocode all issuers that dont already have coordinates"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force geocoding for all issuers, even those that already have coordinates",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.0,
            help="Delay in seconds between geocoding requests (default and minimum: 1.0)",
        )

    def handle(self, *args, **options):
        force = options["force"]
        delay = options["delay"]

        if force:
            issuers = Issuer.objects.all()
            self.stdout.write(f"Processing all {issuers.count()} issuers")
        else:
            issuers = Issuer.objects.filter(
                models.Q(lat__isnull=True) | models.Q(lon__isnull=True)
            )
            self.stdout.write(
                f"Processing {issuers.count()} issuers without coordinates"
            )

        if not issuers.exists():
            self.stdout.write(self.style.SUCCESS("No issuers need geocoding!"))
            return

        nom = Nominatim(user_agent="OpenEducationalBadges")

        successful = 0
        failed = 0

        for issuer in issuers:
            addr_string = (
                (issuer.street if issuer.street is not None else "")
                + " "
                + (str(issuer.streetnumber) if issuer.streetnumber is not None else "")
                + " "
                + (str(issuer.zip) if issuer.zip is not None else "")
                + " "
                + (str(issuer.city) if issuer.city is not None else "")
                + " Deutschland"
            ).strip()

            if not addr_string:
                self.stdout.write(
                    self.style.WARNING(f"Issuer {issuer.pk}: No address information")
                )
                failed += 1
                continue

            self.stdout.write(f"Geocoding issuer {issuer.pk}: {addr_string}")

            try:
                # Add delay to respect rate limits
                if not delay or delay < 1.0:
                    self.style.WARNING(f"A delay of less than 1s violates rate limits; setting to 1s")
                    delay = 1.0
                time.sleep(delay)

                geoloc = nom.geocode(addr_string)

                if geoloc:
                    issuer.lat = geoloc.latitude
                    issuer.lon = geoloc.longitude
                    # Use update_fields to avoid triggering the save() method's geocoding logic
                    issuer.save(update_fields=["lat", "lon"])

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Success: {geoloc.latitude}, {geoloc.longitude}"
                        )
                    )
                    successful += 1
                else:
                    self.stdout.write(self.style.WARNING("✗ No geocoding result found"))
                    failed += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Error: {e}"))
                failed += 1

        self.stdout.write(f"\nCompleted! Successful: {successful}, Failed: {failed}")

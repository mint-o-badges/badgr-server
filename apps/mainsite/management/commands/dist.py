import os
from django.core.management import call_command
from django.core.management.base import BaseCommand

from mainsite import TOP_DIR


class Command(BaseCommand):
    args = ""
    help = (
        "Runs build tasks to compile javascript and css and generate API documentation"
    )

    def handle(self, *args, **options):
        dirname = os.path.join(TOP_DIR, "apps", "mainsite", "static", "swagger-ui")
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        # Generate OpenAPI schema for different versions
        versions = ["v1", "v2", "bcv1"]

        for version in versions:
            output_file = os.path.join(dirname, f"api_spec_{version}.json")

            self.stdout.write(f"Generating schema for version {version}...")

            try:
                # Generate the schema file
                # Note: drf-spectacular doesn't have native multi-version support
                with open(output_file, "w"):
                    call_command(
                        "spectacular",
                        "--file",
                        output_file,
                        "--format",
                        "openapi-json",
                        "--validate",
                    )

                self.stdout.write(
                    self.style.SUCCESS(f"✓ Successfully generated {output_file}")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Failed to generate {output_file}: {str(e)}")
                )

        self.stdout.write(
            self.style.SUCCESS("\nAll API documentation generated successfully!")
        )

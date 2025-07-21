from django.core.management.base import BaseCommand
from django.db import transaction
from issuer.models import Issuer, BadgeInstance
from issuer.utils import generate_private_key_pem
from collections import Counter


class Command(BaseCommand):
    help = "Regenerate private keys for issuers with duplicate keys and rebake affected assertions"

    def handle(self, *args, **options):
        self.stdout.write("Analyzing private keys for duplicates...")

        all_keys = list(Issuer.objects.values_list("private_key", flat=True))
        key_counts = Counter(all_keys)
        duplicate_keys = [key for key, count in key_counts.items() if count > 1]

        if not duplicate_keys:
            self.stdout.write(self.style.SUCCESS("No duplicate private keys found."))
            return

        affected_issuers = Issuer.objects.filter(private_key__in=duplicate_keys)
        affected_issuer_ids = list(affected_issuers.values_list("id", flat=True))

        affected_assertions = BadgeInstance.objects.filter(
            issuer_id__in=affected_issuer_ids, ob_json_3_0__isnull=False
        )

        self.stdout.write(f"Found {len(duplicate_keys)} duplicate private keys")
        self.stdout.write(f"Affecting {affected_issuers.count()} issuers")
        self.stdout.write(f"Need to rebake {affected_assertions.count()} assertions")

        self._regenerate_keys_and_rebake(affected_issuers, affected_assertions)

    def _regenerate_keys_and_rebake(self, affected_issuers, affected_assertions):
        with transaction.atomic():
            self.stdout.write("Regenerating private keys...")

            for issuer in affected_issuers:
                issuer.private_key = generate_private_key_pem()
                issuer.save()

            self.stdout.write(f"\nRebaking {affected_assertions.count()} assertions...")

            proof_unchanged_count = 0
            proof_changed_count = 0
            failed_assertions = []
            no_proof_count = 0

            for i, assertion in enumerate(affected_assertions, 1):
                if i % 10 == 0:
                    self.stdout.write(f"  Progress: {i}/{affected_assertions.count()}")

                try:
                    original_json = assertion.get_json_3_0()
                    original_proof_value = None

                    if "proof" in original_json and len(original_json["proof"]) > 0:
                        original_proof_value = original_json["proof"][0].get(
                            "proofValue"
                        )

                    assertion.rebake()

                    new_json = assertion.get_json_3_0()
                    new_proof_value = None

                    if "proof" in new_json and len(new_json["proof"]) > 0:
                        new_proof_value = new_json["proof"][0].get("proofValue")

                    if original_proof_value and new_proof_value:
                        if original_proof_value == new_proof_value:
                            proof_unchanged_count += 1
                            self.stdout.write(
                                self.style.WARNING(
                                    f"ProofValue unchanged for assertion {assertion.id}"
                                )
                            )
                        else:
                            proof_changed_count += 1
                    else:
                        no_proof_count += 1

                except Exception as e:
                    failed_assertions.append(assertion.entity_id)
                    self.stdout.write(
                        self.style.ERROR(
                            f"Failed to rebake assertion {assertion.entity_id}: {str(e)}"
                        )
                    )

            self.stdout.write(f"\n{self.style.SUCCESS('OPERATION COMPLETE')}")
            self.stdout.write(f"Assertions with changed proofs: {proof_changed_count}")
            self.stdout.write(
                f"Assertions with unchanged proofs: {proof_unchanged_count}"
            )
            self.stdout.write(f"Assertions without proof comparison: {no_proof_count}")

            if failed_assertions:
                self.stdout.write(
                    self.style.ERROR(
                        f"Failed assertions: {len(failed_assertions)} "
                        f"(IDs: {', '.join(map(str, failed_assertions))})"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS("All assertions rebaked successfully!")
                )

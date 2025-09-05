from django.core.management.base import BaseCommand, CommandParser
from allauth.account.adapter import get_adapter


class Command(BaseCommand):
    """Send a test email using the specified template"""

    help = "Send a test email using the specified template"

    def add_arguments(self, parser: CommandParser) -> None:
        super().add_arguments(parser)
        parser.add_argument(
            "--to", type=str, help="Address to send the test mail to", required=True
        )
        parser.add_argument(
            "--template", type=str, help="Email template to use", required=True
        )
        parser.add_argument(
            "extras", nargs="*", type=str, help="Extra arguments as key=value pairs"
        )

    def handle(self, *args, **kwargs) -> None:
        to = kwargs["to"]
        template = kwargs["template"]
        # build the context from the extras
        extras_list = kwargs["extras"]
        ctx = dict(pair.split("=", 1) for pair in extras_list if "=" in pair)
        self.stdout.write(f"Sending email template '{template}' to {to}")
        self.stdout.write(f"Context: {ctx}")

        get_adapter().send_mail(template, to, ctx)

        self.stdout.write("Sent!")

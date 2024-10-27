from django.core.management.base import BaseCommand
from badgeuser.models import BadgeUser, CachedEmailAddress
import os

class Command(BaseCommand):
    def handle(self, *args, **options):
        users = BadgeUser.objects.all()
        file_path = os.path.join(os.getcwd(), 'user_emails.txt')
        try:
            with open(file_path, 'w') as f:
             for user in users:
                         f.write(f"Name: {user.first_name} {user.last_name}, Email: {user.primary_email}\n")
             self.stdout.write(self.style.SUCCESS(f'Successfully exported emails to {file_path}'))
        except Exception as e:
              self.stdout.write(self.style.ERROR(f'An error occurred: {str(e)}'))

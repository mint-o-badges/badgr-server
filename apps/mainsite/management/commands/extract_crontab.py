from django.core.management.base import BaseCommand
import os

class Command(BaseCommand):
    help = 'Extract current crontab into a file for Supercronic'

    def handle(self, *args, **kwargs):
        os.system('crontab -l > crontab')
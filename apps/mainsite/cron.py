from oauth2_provider.models import clear_expired
from django_cron import CronJobBase, Schedule

class MyCronJob(CronJobBase):
    RUN_EVERY_MINS = 1 

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'mainsite.MyCronJob'    

    def do(self):
        clear_expired()   
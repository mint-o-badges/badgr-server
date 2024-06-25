from oauth2_provider.models import clear_expired
from django_cron import CronJobBase, Schedule

class MyCronJob(CronJobBase):
    RUN_EVERY_MINS = 1 

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'mainsite.my_cron_job'    

    def do(self):
        clear_expired   


# def daily_cron():
#     print("Running daily cron")
#     clear_expired()
#     print("Finished daily cron")
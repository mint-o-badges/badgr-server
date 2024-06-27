#!/bin/sh

# Start the cron service
service cron start

# add cronjobs
/badgr_server/manage.py crontab remove
/badgr_server/manage.py crontab add

# Start the Django server
exec /badgr_server/manage.py runserver 0.0.0.0:8000




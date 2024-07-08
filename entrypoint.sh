#!/bin/sh

set -e

# Start the cron service
service cron start

# add cronjobs
/badgr_server/manage.py crontab remove
/badgr_server/manage.py crontab add

# apply migrations
/badgr_server/manage.py migrate

# Start the Django server
exec uwsgi --socket sock/app.sock --ini uwsgi.ini
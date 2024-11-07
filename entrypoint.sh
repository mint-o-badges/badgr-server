#!/bin/sh

set -e

/badgr_server/manage.py migrate
/badgr_server/manage.py collectstatic --noinput


supercronic /etc/cron.d/crontab &

# Start the Django server
exec uwsgi --socket sock/app.sock --ini uwsgi.ini
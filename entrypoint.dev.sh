#!/bin/sh

set -e

/badgr_server/manage.py migrate
/badgr_server/manage.py dist
/badgr_server/manage.py collectstatic --noinput

supercronic /etc/cron.d/crontab &

# Start the Django server
exec /badgr_server/manage.py runserver 0.0.0.0:8000


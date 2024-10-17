#!/bin/sh

set -e

/badgr_server/manage.py migrate
/badgr_server/manage.py collectstatic --noinput

/badgr_server/manage.py crontab remove
/badgr_server/manage.py crontab add

/badgr_server/manage.py extract_crontab

supercronic crontab &

# Start the Django server
exec uwsgi --socket sock/app.sock --ini uwsgi.ini
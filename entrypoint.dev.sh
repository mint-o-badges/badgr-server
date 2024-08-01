#!/bin/sh

set -e

/badgr_server/manage.py migrate
/badgr_server/manage.py collectstatic --noinput

# Start the Django server
exec /badgr_server/manage.py runserver 0.0.0.0:8000




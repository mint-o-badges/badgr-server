#!/bin/sh

# If this is going to be a cron container, set up the crontab.
if [ "$1" = cron ]; then
  python manage.py crontab remove
  python manage.py crontab add
fi

# Launch the main container command passed as arguments.
exec "$@"

# touch /var/log/cron.log
# declare -p | grep -Ev 'BASHOPTS|BASH_VERSINFO|EUID|PPID|SHELLOPTS|UID' > /etc/environment

# python manage.py crontab remove
# python manage.py crontab add

# BASH_ENV=/etc/environment

# # Start cron service
# service cron start

# # Start Django server
# python manage.py runserver 0.0.0.0:8000

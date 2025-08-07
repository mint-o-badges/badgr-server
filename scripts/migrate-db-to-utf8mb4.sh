#!/bin/bash

echo "########## Creating backup"
docker compose exec api python manage.py dbbackup

echo "########## Migrating database"
docker compose exec -T db mysql -u root --password=password badgr < ./scripts/migrate-db-to-utf8mb4.sql

echo "########## Performing checks on migrated db"
docker compose exec db mysqlcheck -u root --password=password --auto-repair --optimize badgr
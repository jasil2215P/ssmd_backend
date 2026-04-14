#!/bin/bash
export ENVIRONMENT="production"

echo "Running migrations..."
alembic upgrade head

exec gunicorn main:app -c gunicorn.conf.py

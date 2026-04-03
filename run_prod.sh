#!/bin/bash
export ENVIRONMENT="production"
exec gunicorn main:app -c gunicorn.conf.py

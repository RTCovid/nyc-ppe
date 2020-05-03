#!/bin/bash
set -e

python manage.py migrate
python manage.py collectstatic
pipenv run gunicorn -t 120 -b 0.0.0.0:8000 nyc_data.wsgi

#!/bin/bash
set -e

python manage.py migrate
python manage.py collectstatic
pipenv run gunicorn -b 0.0.0.0:8000 nyc_data.wsgi

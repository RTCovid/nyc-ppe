# nyc-ppe
Pretty normal Django app, dockerized dev environment. Do _not_ put any data in this repo.

Build and exec into the container:
```bash
docker-compose build
docker-compose up -d
docker-compose exec backend bash
```

Standard django stuff:
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```
Then http://localhost:8000

## Import Data
1. Create a directory called `private-data` at the repo root (automatically gitignored)
2. Copy in all your spreadsheets. Names don't matter!
2. `docker-compose exec backend bash`
3. `python manage.py runscript ppe_import`

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
```

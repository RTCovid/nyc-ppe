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

## Import Data
1. Create a directory called `private-data` at the repo root (automatically gitignored)
2. Insert the PPE spreadsheet at `ppe_orders.xlsx`
3. `cd nyc_data`
3. `python manage.py runscript ppe_import`

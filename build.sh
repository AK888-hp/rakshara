#!/usr/bin/env bash
# Exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate#!/usr/bin/env bash
# Exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# This line will run create_superuser non-interactively
# It will only create the user the *first* time it's run
python manage.py createsuperuser --noinput || echo "Superuser already exists."
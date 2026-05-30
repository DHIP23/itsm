# build.sh (à la racine du projet)
#!/usr/bin/env bash
set -o errexit   # Arrêter si une commande échoue

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
python setup_initial.py
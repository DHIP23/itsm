@echo off
call venv\Scripts\activate
python manage.py collectstatic --noinput
waitress-serve --host=0.0.0.0 --port=8000 dsi_itsm.wsgi:application
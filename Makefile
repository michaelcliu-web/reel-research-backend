all:
	python3 manage.py makemigrations
	python3 manage.py migrate
	python3 manage.py runserver 8005

migrations:
	python3 manage.py makemigrations

migrate:
	python3 manage.py migrate

cleardb:
	python3 manage.py cleardb

fakedata:
	python3 manage.py create_fake_data

superuser:
	python3 manage.py createsuperuser --noinput

install:
	( \
		python3 -m venv venv; \
		source venv/bin/activate; \
		pip install -r requirements.txt; \
		python3 manage.py createsuperuser --noinput; \
	)



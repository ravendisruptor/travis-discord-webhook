release: cp config.yaml.example config.yaml
web: gunicorn -w 4 -b "0.0.0.0:$PORT" app:app

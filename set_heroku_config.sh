#!/bin/bash

# Set required environment variables
heroku config:set FLASK_SECRET_KEY="$FLASK_SECRET_KEY" --app brandocs-databank
heroku config:set BASIC_AUTH_USERNAME="$BASIC_AUTH_USERNAME" --app brandocs-databank
heroku config:set BASIC_AUTH_PASSWORD="$BASIC_AUTH_PASSWORD" --app brandocs-databank
heroku config:set EMAIL_USERNAME="$EMAIL_USERNAME" --app brandocs-databank
heroku config:set EMAIL_PASSWORD="$EMAIL_PASSWORD" --app brandocs-databank
heroku config:set EMAIL_SERVER="$EMAIL_SERVER" --app brandocs-databank

# Set optional SQLAlchemy pool configuration with default values
heroku config:set SQLALCHEMY_POOL_SIZE=5 --app brandocs-databank
heroku config:set SQLALCHEMY_MAX_OVERFLOW=10 --app brandocs-databank
heroku config:set SQLALCHEMY_POOL_TIMEOUT=30 --app brandocs-databank
heroku config:set SQLALCHEMY_POOL_RECYCLE=280 --app brandocs-databank

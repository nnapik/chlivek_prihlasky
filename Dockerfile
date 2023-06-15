FROM python:slim

RUN apt-get clean \
    && apt-get -y update \
    && apt-get -y install python3-dev build-essential 

WORKDIR /srv/flask_app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY uwsgi.ini ./
COPY static/* ./static/
COPY templates/* ./templates/
COPY prihlasky.py ./
CMD ["uwsgi", "--ini", "uwsgi.ini"]
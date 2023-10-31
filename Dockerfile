FROM python:3

RUN apt-get clean \
    && apt-get -y update \
    && apt-get -y install python3-dev build-essential 

WORKDIR /srv/flask_app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY static/* ./static/
COPY templates/* ./templates/
COPY prihlasky.py ./
CMD ["gunicorn", "-w", "4", "prihlasky:app"]

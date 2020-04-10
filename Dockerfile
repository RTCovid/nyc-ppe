FROM python:3.8-slim

RUN apt-get update && apt-get install -y \
    curl \
    wget \
    vim \
    software-properties-common

RUN pip install pipenv

WORKDIR /app
COPY Pipfile /app/
COPY Pipfile.lock /app/
RUN pipenv install --pre --system --deploy


COPY . /app

ENV PYTHONPATH /

WORKDIR /app/nyc_data

CMD ["./launch.sh"]

EXPOSE 8000
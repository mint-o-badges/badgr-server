# Best practies taken from here: https://snyk.io/blog/best-practices-containerizing-python-docker/

# ------------------------------> Build image
FROM python:3.8.14-slim-buster as build
RUN apt-get update
RUN apt-get install -y default-libmysqlclient-dev \
                       python3-dev \
                       python3-cairo \
                       build-essential \
                       xmlsec1 \
                       libxmlsec1-dev \
                       pkg-config

RUN mkdir /badgr_server
WORKDIR /badgr_server
RUN python -m venv /badgr_server/venv
ENV PATH="/badgr_server/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt

# ------------------------------> Final image
FROM python:3.8.14-slim-buster
RUN apt-get update
RUN apt-get install -y default-libmysqlclient-dev \
                       python3-cairo \
                       libxml2

RUN groupadd -g 999 python && \
    useradd -r -u 999 -g python python

RUN mkdir /badgr_server && chown python:python /badgr_server
WORKDIR /badgr_server

# Copy installed dependencies
COPY --chown=python:python --from=build /badgr_server/venv /badgr_server/venv

# Copy everything related Django stuff
COPY --chown=python:python  manage.py                          .
COPY --chown=python:python  .docker/etc/uwsgi.ini              .
COPY --chown=python:python  .docker/etc/wsgi.py                .
COPY --chown=python:python  apps                               ./apps
COPY --chown=python:python  .docker/etc/settings_local.py      ./apps/mainsite/settings_local.py
# delete this comment

USER 999

ENV PATH="/badgr_server/venv/bin:$PATH"
CMD ["uwsgi","--socket", "sock/app.sock", "--ini", "uwsgi.ini"]
FROM python:3.12.7-alpine3.20
LABEL maintainer="eimeredelin@sberbank.ru"

# It is highly recommended to set the MPLCONFIGDIR environment variable
# to a writable directory, in particular to speed up the import of Matplotlib
# and to better support multiprocessing.
# Default is /.config/matplotlib/ and it's not writable.

ENV MPLCONFIGDIR=/tmp/matplotlib

# https://wiki.alpinelinux.org/wiki/Fonts
# https://unix.stackexchange.com/questions/438257

RUN apk --no-cache add msttcorefonts-installer fontconfig \
    && update-ms-fonts \
    && fc-cache -f

WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./app /code/app

# FastAPI requirement: write CMD in exec form, do not use shell form
# https://fastapi.tiangolo.com/deployment/docker/#use-cmd-exec-form

# Cloud.ru Container Apps requirement:
# do not run container on port 8012, 8013, 8022, 8112, 9090, 9091, 1-1024

CMD ["fastapi", "run", "app/main.py", "--port", "1704"]

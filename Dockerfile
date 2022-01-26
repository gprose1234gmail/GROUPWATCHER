FROM python:3.9.6-alpine

RUN apk update

RUN apk add --no-cache \
    git \
    postgresql-libs \
    jpeg-dev \
    imagemagick

RUN apk add --no-cache --virtual .build-deps \
    git \
    gcc \
    g++ \
    musl-dev \
    postgresql-dev \
    libffi-dev \
    libwebp-dev \
    zlib-dev \
    imagemagick-dev \
    msttcorefonts-installer \
    fontconfig

# Rust Compiler
RUN apk add cargo

RUN update-ms-fonts && \
    fc-cache -f

RUN mkdir /data

RUN chmod 777 /data
RUN git clone https://github.com/thedeveloper12/GroupHelper.git -b main /data/GroupHalper

RUN pip install -r /data/GroupHalper/requirements.txt
RUN apk del .build-deps



WORKDIR /data/GroupHalper
CMD ["python", "-m", "group_helper"]
FROM python:3.14 AS python-base
FROM python-base AS builder-base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    \
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv" \
    \
    DOCKER=true \
    GIT_PYTHON_REFRESH=quiet

RUN apt-get update && \
    apt-get install -y wget gnupg2 \

RUN apt-get update && apt-get upgrade -y && apt-get install --no-install-recommends -y \
    build-essential \
    curl \
    ffmpeg \
    gcc \
    git \
    libavcodec-dev \
    libavdevice-dev \
    libavformat-dev \
    libavutil-dev \
    libcairo2 \
    libmagic1 \
    libswscale-dev \
    openssl \
    openssh-server \
    python3 \
    python3-dev \
    python3-pip \
    xfonts-75dpi \
    xfonts-base \

RUN curl -sL https://deb.nodesource.com/setup_18.x -o nodesource_setup.sh && \
    bash nodesource_setup.sh && \
    apt-get install -y nodejs && \
    rm nodesource_setup.sh
RUN rm -rf /var/lib/apt/lists/ /var/cache/apt/archives/ /tmp/*

WORKDIR /data
RUN mkdir /data/private

RUN git clone https://github.com/coddrago/Heroku /data/Heroku
WORKDIR /data/Heroku
ARG HEROKU_REF=beta
RUN git fetch origin "${HEROKU_REF}" && git checkout "${HEROKU_REF}" && git pull origin "${HEROKU_REF}"

RUN pip install --no-warn-script-location --no-cache-dir -U -r requirements.txt

CMD ["python", "-m", "heroku", "--root"]

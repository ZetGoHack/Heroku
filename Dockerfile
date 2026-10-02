FROM ghcr.io/astral-sh/uv:latest AS uv

FROM python:3.14

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    DOCKER=true \
    GIT_PYTHON_REFRESH=quiet \
    UV_SYSTEM_PYTHON=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

COPY --from=uv /uv /uvx /bin/

RUN apt-get update && apt-get install --no-install-recommends -y \
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
    openssh-server \
    xfonts-75dpi \
    xfonts-base \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install --no-install-recommends -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# /data is the runtime data root (kept in a volume), /app holds the code.
RUN mkdir -p /data/private /app

WORKDIR /app

# Install dependencies first so Docker can cache this layer
COPY requirements.txt .
RUN uv pip install --no-cache -r requirements.txt

# Copy the local project instead of cloning it from GitHub
COPY . .

CMD ["python", "-m", "heroku", "--root"]

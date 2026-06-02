#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Heroku"
MODULE_NAME="heroku"
REPO_URL="${HEROKU_REPO_URL:-https://github.com/coddrago/Heroku.git}"
VENV_DIR="${HEROKU_VENV_DIR:-.venv}"
LOG_FILE="heroku-install.log"

if [ "${SUDO_USER:-}" != "" ] && command -v sudo >/dev/null 2>&1; then
	RUN_AS_USER=(sudo -u "$SUDO_USER")
else
	RUN_AS_USER=()
fi

info() {
	printf "\033[0;34m%s\033[0m\n" "$1"
}

ok() {
	printf "\033[0;32m%s\033[0m\n" "$1"
}

fail() {
	printf "\033[1;31m%s\033[0m\n" "$1" >&2
	[ -f "$LOG_FILE" ] && cat "$LOG_FILE" >&2
	exit "${2:-1}"
}

run() {
	"$@" >>"$LOG_FILE" 2>&1
}

sudo_run() {
	if [ "$(id -u)" -eq 0 ]; then
		run "$@"
	elif command -v sudo >/dev/null 2>&1; then
		run sudo "$@"
	else
		fail "Root privileges or sudo are required to install system packages." 2
	fi
}

python_cmd() {
	if command -v python3 >/dev/null 2>&1; then
		printf "python3"
	elif command -v python >/dev/null 2>&1; then
		printf "python"
	else
		fail "Python is not installed." 2
	fi
}

install_system_packages() {
	info "Installing system packages..."

	if echo "${OSTYPE:-}" | grep -qE "^linux-android"; then
		run pkg update -y
		run pkg install -y \
			build-essential \
			ffmpeg \
			git \
			libcairo \
			libffi \
			libjpeg-turbo \
			libwebp \
			ncurses-utils \
			openssl \
			python
	elif command -v apt-get >/dev/null 2>&1; then
		sudo_run apt-get update
		sudo_run apt-get install -y \
			build-essential \
			ffmpeg \
			git \
			imagemagick \
			libcairo2 \
			libffi-dev \
			libjpeg-dev \
			libmagic1 \
			libopenjp2-7 \
			libtiff-dev \
			libwebp-dev \
			libz-dev \
			python3 \
			python3-dev \
			python3-pip \
			python3-venv
	elif command -v pacman >/dev/null 2>&1; then
		sudo_run pacman -Sy --needed --noconfirm \
			base-devel \
			ffmpeg \
			file \
			git \
			imagemagick \
			python \
			python-pip
	elif command -v dnf >/dev/null 2>&1; then
		sudo_run dnf install -y \
			ffmpeg \
			file-libs \
			gcc \
			gcc-c++ \
			git \
			imagemagick \
			python3 \
			python3-devel \
			python3-pip
	elif command -v brew >/dev/null 2>&1; then
		run brew install git jpeg webp
	else
		info "Unknown package manager, skipping system package installation."
	fi
}

check_python() {
	local py="$1"

	"$py" - <<'PY'
import sys

if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required")
PY
}

prepare_repo() {
	if [ -d "$MODULE_NAME" ] && [ -f "requirements.txt" ]; then
		return
	fi

	if [ -d "$APP_NAME/$MODULE_NAME" ]; then
		cd "$APP_NAME"
		return
	fi

	info "Cloning repo..."
	rm -rf "$APP_NAME"
	"${RUN_AS_USER[@]}" git clone "$REPO_URL" "$APP_NAME" >>"$LOG_FILE" 2>&1 || fail "Clone failed." 3
	cd "$APP_NAME"
}

create_venv() {
	local py="$1"

	info "Creating virtual environment..."
	"${RUN_AS_USER[@]}" "$py" -m venv "$VENV_DIR" >>"$LOG_FILE" 2>&1 || fail "Virtual environment creation failed." 4
}

install_python_packages() {
	local venv_python="$VENV_DIR/bin/python"

	info "Installing Python dependencies..."
	"${RUN_AS_USER[@]}" "$venv_python" -m pip install --upgrade pip setuptools wheel >>"$LOG_FILE" 2>&1 || fail "Pip upgrade failed." 4
	"${RUN_AS_USER[@]}" "$venv_python" -m pip install --upgrade -r requirements.txt --disable-pip-version-check >>"$LOG_FILE" 2>&1 || fail "Requirements installation failed." 4
}

start_app() {
	info "Starting..."
	"${RUN_AS_USER[@]}" "$VENV_DIR/bin/python" -m "$MODULE_NAME" "$@"
}

clear || true
cat assets/download.txt
printf "\033[3;34;40m Installing %s...\033[0m\n\n" "$APP_NAME"

: >"$LOG_FILE"

if [ "${SUDO_USER:-}" != "" ]; then
	chown "$SUDO_USER:" "$LOG_FILE" >/dev/null 2>&1 || true
fi

install_system_packages
PYTHON="$(python_cmd)"
prepare_repo
check_python "$PYTHON"
create_venv "$PYTHON"
install_python_packages

touch .setup_complete
rm -f "$LOG_FILE"

ok "Installation complete."
start_app "$@"

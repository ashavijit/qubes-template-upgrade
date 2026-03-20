#!/usr/bin/env bash

set -euo pipefail

: "${TARGET_VERSION:?TARGET_VERSION must be set}"
: "${TARGET_CODENAME:?TARGET_CODENAME must be set}"

log() { echo "[debian-agent] $*" >&2; }

export DEBIAN_FRONTEND=noninteractive

CURRENT=$(cat /etc/debian_version | cut -d. -f1)
if [ "$CURRENT" -ge "$TARGET_VERSION" ]; then
    log "Already at Debian $CURRENT, nothing to do"
    exit 0
fi

if ! grep -q "$TARGET_CODENAME" /etc/apt/sources.list 2>/dev/null && \
   ! grep -rq "$TARGET_CODENAME" /etc/apt/sources.list.d/ 2>/dev/null; then
    log "ERROR: sources.list does not contain $TARGET_CODENAME"
    log "The orchestrator should have updated sources before running this agent"
    exit 1
fi

log "apt sources confirmed for $TARGET_CODENAME"

log "Running apt-get update"
sudo apt-get update

log "Running apt-get upgrade (minimal)"
sudo apt-get upgrade -y \
    -o Dpkg::Options::="--force-confnew" \
    -o Dpkg::Options::="--force-confdef"

log "Running apt-get dist-upgrade"
sudo apt-get dist-upgrade -y \
    -o Dpkg::Options::="--force-confnew" \
    -o Dpkg::Options::="--force-confdef"

log "Removing unused packages"
sudo apt-get autoremove -y
sudo apt-get autoclean -y

log "Trimming filesystem"
sudo fstrim -av || true

log "Debian $TARGET_VERSION ($TARGET_CODENAME) upgrade complete"

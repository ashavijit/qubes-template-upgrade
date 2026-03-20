#!/usr/bin/env bash

set -euo pipefail

: "${TARGET_VERSION:?TARGET_VERSION must be set}"
: "${CACHE_MOUNT:=/mnt/removable}"
: "${BLOCK_DEV:=/dev/xvdi}"

log() { echo "[fedora-agent] $*" >&2; }

log "Formatting cache disk $BLOCK_DEV"
sudo mkfs.ext4 -F "$BLOCK_DEV"

log "Mounting cache disk at $CACHE_MOUNT"
sudo mkdir -p "$CACHE_MOUNT"
sudo mount "$BLOCK_DEV" "$CACHE_MOUNT"

cleanup() {
    log "Unmounting cache disk"
    sudo umount "$CACHE_MOUNT" 2>/dev/null || true
}
trap cleanup EXIT

log "Cleaning dnf cache"
sudo dnf clean all

log "Running dnf upgrade (pass 1)"
sudo dnf upgrade --best -y

log "Running dnf distro-sync to Fedora $TARGET_VERSION"
sudo dnf \
    --releasever="$TARGET_VERSION" \
    --setopt="cachedir=$CACHE_MOUNT" \
    --best \
    distro-sync \
    --allowerasing \
    -y

log "Removing unused packages"
sudo dnf autoremove -y || true

log "Trimming filesystem"
sudo fstrim -av || true

log "Fedora $TARGET_VERSION upgrade complete"

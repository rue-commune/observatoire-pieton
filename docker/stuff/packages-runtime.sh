#!/bin/bash
set -euo pipefail

echo; echo "==== packages-runtime.sh ===="

export DEBIAN_FRONTEND=noninteractive

apt-get update

# git: Hugo's enableGitInfo and module support.
# gosu: drop privileges in entrypoint.sh after UID/GID mapping.
# python3-*: the data generator in scripts/data and its tests.
apt-get install -y --no-install-recommends     \
    ca-certificates                             \
    curl                                        \
    git                                         \
    gosu                                        \
    python3                                     \
    python3-pyproj                              \
    python3-shapely                             \

rm -rf /var/lib/apt/lists/*

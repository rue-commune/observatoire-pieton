#!/bin/bash
set -euo pipefail

echo; echo "==== packages-dev.sh ===="

export DEBIAN_FRONTEND=noninteractive

apt-get update

# Development tools for the interactive shell
# black, flake8: Python style checks in scripts/test.sh.
apt-get install -y --no-install-recommends     \
    black                                       \
    emacs-nox                                   \
    fd-find                                     \
    flake8                                      \
    jq                                          \
    less                                        \
    procps                                      \
    ripgrep                                     \
    rsync                                       \

rm -rf /var/lib/apt/lists/*

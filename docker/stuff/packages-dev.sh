#!/bin/bash
set -euo pipefail

echo; echo "==== packages-dev.sh ===="

export DEBIAN_FRONTEND=noninteractive

apt-get update

# Development tools for the interactive shell
apt-get install -y --no-install-recommends     \
    emacs-nox                                   \
    fd-find                                     \
    jq                                          \
    less                                        \
    procps                                      \
    ripgrep                                     \
    rsync                                       \

rm -rf /var/lib/apt/lists/*

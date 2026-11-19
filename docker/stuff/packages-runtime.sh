#!/bin/bash
set -euo pipefail

echo; echo "==== packages-runtime.sh ===="

export DEBIAN_FRONTEND=noninteractive

apt-get update

# git: Hugo's enableGitInfo and module support.
# gosu: drop privileges in entrypoint.sh after UID/GID mapping.
# nodejs: unit tests for the Cloudflare Pages Functions (node --test).
apt-get install -y --no-install-recommends     \
    ca-certificates                             \
    curl                                        \
    git                                         \
    gosu                                        \
    nodejs                                      \

rm -rf /var/lib/apt/lists/*

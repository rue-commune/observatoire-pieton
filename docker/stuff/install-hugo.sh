#!/bin/bash
# Install a pinned Hugo extended release from GitHub, verifying its
# SHA-256 against a sum pinned in the Dockerfile.
set -euo pipefail

version="${1:?usage: install-hugo.sh VERSION SHA256_AMD64 SHA256_ARM64}"
sha256_amd64="${2:?missing amd64 SHA-256}"
sha256_arm64="${3:?missing arm64 SHA-256}"
arch="$(dpkg --print-architecture)"
case "$arch" in
    amd64) expected="$sha256_amd64" ;;
    arm64) expected="$sha256_arm64" ;;
    *) echo "Unsupported architecture for Hugo extended: $arch" >&2; exit 1 ;;
esac

tarball="hugo_extended_${version}_linux-${arch}.tar.gz"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

cd "$work_dir"
curl -fsSLO "https://github.com/gohugoio/hugo/releases/download/v${version}/$tarball"
echo "$expected  $tarball" | sha256sum -c -
tar -xzf "$tarball" hugo
install -m 755 hugo /usr/local/bin/hugo
hugo version

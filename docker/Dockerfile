FROM ubuntu:26.04 AS hugo-dev-base

WORKDIR /devsrc

# Install runtime packages
# These COPY commands only invalidate cache if the copied file has changed
COPY --chmod=755 docker/stuff/packages-runtime.sh /usr/local/lib/docker-setup/
RUN bash -o pipefail -c '/usr/local/lib/docker-setup/packages-runtime.sh 2>&1 | tee /var/packages-runtime.out'

# Install development packages
COPY --chmod=755 docker/stuff/packages-dev.sh /usr/local/lib/docker-setup/
RUN bash -o pipefail -c '/usr/local/lib/docker-setup/packages-dev.sh 2>&1 | tee /var/packages-dev.out'

# Install a pinned Hugo extended release. Ubuntu's packaged Hugo lags
# upstream, so it is not used. The SHA-256 sums are pinned here rather than
# trusted from the release itself, so a tampered release fails the build.
# When upgrading, take them from hugo_<version>_checksums.txt.
ARG HUGO_VERSION=0.170.1
ARG HUGO_SHA256_AMD64=841a5462853aefc9942e4de1e8a5d75584b6a5181941e6ad3f1d745190e03cd8
ARG HUGO_SHA256_ARM64=6f57f13bc47c000c0d36c7f5a446d6c06f7956d8e102cc2a13735e0c0225b2d2
COPY --chmod=755 docker/stuff/install-hugo.sh /usr/local/lib/docker-setup/
RUN /usr/local/lib/docker-setup/install-hugo.sh "$HUGO_VERSION" \
        "$HUGO_SHA256_AMD64" "$HUGO_SHA256_ARM64"

# Create dev user for non-root operations
RUN useradd -ms /bin/bash dev

# Add entrypoint script for UID/GID mapping
COPY --chmod=755 docker/stuff/entrypoint.sh /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]


FROM hugo-dev-base AS hugo-dev

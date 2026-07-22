FROM docker.io/library/python@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b AS python-runtime

FROM mcr.microsoft.com/devcontainers/base@sha256:36c0ae9fe6bfa914cf7eb05b08b09a3a31961dc76eed6fbb75179382c817582c

# Copy the reviewed prebuilt CPython runtime instead of compiling it during
# every Dev Container build. The source image digest and executable digest are
# both enforced by the root supply-chain validator and post-create bootstrap.
COPY --from=python-runtime /usr/local/ /usr/local/

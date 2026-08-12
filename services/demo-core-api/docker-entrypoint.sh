#!/bin/sh
set -eu

# A named Docker volume hides the ownership prepared at image-build time.
# Repair only the dedicated SQLite directory, then run the API unprivileged.
chown -R acme:acme /app/data
exec runuser -u acme -- "$@"

#!/bin/sh
set -eu

# The named volume is root-owned on first mount. Restrict ownership repair to
# the dedicated AI state directory, then run the network service unprivileged.
chown -R acme:acme /app/data
exec runuser -u acme -- "$@"

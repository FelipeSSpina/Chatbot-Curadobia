# file: scripts/migrate-models.sh
set -euo pipefail
mkdir -p outputs/models
[ -d models ]  && cp -r models/*  outputs/models/ || true
[ -d modelos ] && cp -r modelos/* outputs/models/ || true

#!/usr/bin/env bash
#
# add-redfish-poller-server.sh  (ROLLBACK)
# Mengembalikan satu entry server (berdasarkan IP) ke list SERVERS
# di dalam redfish_poller.py, menggunakan snapshot yang dibuat oleh
# remove-redfish-poller-server.sh, lalu (opsional) copy ke container.
#
# Penggunaan:
#   ./add-redfish-poller-server.sh <IP>
#
# Variabel environment sama dengan script remove-nya (TARGET_FILE,
# SNAPSHOT_DIR, CONTAINER_NAME, CONTAINER_PATH, COPY_TO_CONTAINER,
# RESTART_CONTAINER).

set -euo pipefail

TARGET_FILE="${TARGET_FILE:-/home/infra/dcim_metrics_project/scripts/redfish_poller.py}"
SNAPSHOT_DIR="${SNAPSHOT_DIR:-/home/infra/dcim_metrics_project/rollback_snapshots}"
CONTAINER_NAME="${CONTAINER_NAME:-dcim-nifi}"
CONTAINER_PATH="${CONTAINER_PATH:-/home/infra/dcim_metrics_project/scripts/redfish_poller.py}"
COPY_TO_CONTAINER="${COPY_TO_CONTAINER:-false}"
RESTART_CONTAINER="${RESTART_CONTAINER:-false}"

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <IP_ADDRESS>"
    exit 1
fi

TARGET_IP="$1"
SNAPSHOT_FILE="$SNAPSHOT_DIR/redfish_poller_${TARGET_IP//./_}.json"

if [[ ! -f "$SNAPSHOT_FILE" ]]; then
    echo "Error: Snapshot tidak ditemukan: $SNAPSHOT_FILE"
    echo "Tidak ada yang bisa direstore otomatis untuk IP $TARGET_IP - cek manual."
    exit 1
fi

if [[ ! -f "$TARGET_FILE" ]]; then
    echo "Error: File tidak ditemukan: $TARGET_FILE"
    exit 1
fi

# Backup file penuh sebelum diedit lagi, untuk audit
BACKUP_FILE="${TARGET_FILE}.bak.$(date +%Y%m%d%H%M%S)"
cp "$TARGET_FILE" "$BACKUP_FILE"
echo "Backup dibuat: $BACKUP_FILE"

python3 - "$TARGET_FILE" "$SNAPSHOT_FILE" <<'PYEOF'
import re
import sys
import json

target_file = sys.argv[1]
snapshot_file = sys.argv[2]

with open(snapshot_file, "r", encoding="utf-8") as f:
    snapshot = json.load(f)

target_ip = snapshot["target_ip"]
entry_text = snapshot["entry_text"]

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

if f'"{target_ip}"' in content:
    print(f"IP {target_ip} sudah ada di dalam file, tidak perlu direstore ulang (skip).")
    sys.exit(0)

pattern = re.compile(r"(?<![A-Za-z_])(SERVERS\s*=\s*\[)(.*?)(\n\])", re.DOTALL)
match = pattern.search(content)

if not match:
    print("Error: Tidak menemukan blok SERVERS = [ ... ] di file.")
    sys.exit(1)

header, body, footer = match.groups()

entries = re.findall(r"\{[^{}]*\}", body)
entries.append(entry_text)

new_body = "\n    " + ",\n    ".join(entries)
new_block = header + new_body + footer

new_content = content[:match.start()] + new_block + content[match.end():]

with open(target_file, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"Entry dengan IP {target_ip} berhasil dikembalikan ke {target_file}")
PYEOF

echo "Selesai mengedit file lokal: $TARGET_FILE"

if [[ "$COPY_TO_CONTAINER" == "true" ]]; then
    echo "Menyalin file ke dalam container '$CONTAINER_NAME' di path '$CONTAINER_PATH'..."
    docker cp "$TARGET_FILE" "${CONTAINER_NAME}:${CONTAINER_PATH}"
    echo "Berhasil disalin ke container."

    if [[ "$RESTART_CONTAINER" == "true" ]]; then
        echo "Merestart container '$CONTAINER_NAME'..."
        docker restart "$CONTAINER_NAME"
        echo "Container direstart."
    fi
else
    echo "Lewati copy ke container (COPY_TO_CONTAINER=false)."
    echo "Untuk menyalin manual: docker cp \"$TARGET_FILE\" \"${CONTAINER_NAME}:${CONTAINER_PATH}\""
fi

# Arsipkan snapshot yang sudah dipakai
mkdir -p "$SNAPSHOT_DIR/used"
mv "$SNAPSHOT_FILE" "$SNAPSHOT_DIR/used/$(basename "$SNAPSHOT_FILE").$(date +%s)"

echo "Selesai."
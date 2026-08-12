#!/usr/bin/env bash
#
# remove-collect-data-server.sh
# Menghapus satu entry server (berdasarkan IP) dari list REDFISH_SERVERS
# di dalam server_inventory_collector.py, menyimpan snapshot entry sebelum dihapus
# (untuk rollback), lalu (opsional) copy hasilnya ke container.
#
# Penggunaan:
#   ./remove-collect-data-server.sh <IP>
#
# Contoh:
#   ./remove-collect-data-server.sh 10.50.0.6
#
# Variabel yang bisa di-override lewat environment:
#   TARGET_FILE       Path file server_inventory_collector.py di host
#                      (default: /home/infra/dcim_metrics_project/scripts/server_inventory_collector.py)
#   SNAPSHOT_DIR       Path folder snapshot untuk rollback
#                      (default: /home/infra/dcim_metrics_project/rollback_snapshots)
#   CONTAINER_NAME     Nama container docker (default: dcim-nifi)
#   CONTAINER_PATH     Path file di dalam container
#                      (default: /home/infra/dcim_metrics_project/scripts/server_inventory_collector.py)
#   COPY_TO_CONTAINER  Set ke "true" untuk otomatis docker cp hasil edit ke container (default: false)
#   RESTART_CONTAINER  Set ke "true" untuk restart container setelah copy (default: false)

set -euo pipefail

# ---------- Konfigurasi default ----------
TARGET_FILE="${TARGET_FILE:-/home/infra/dcim_metrics_project/scripts/server_inventory_collector.py}"
SNAPSHOT_DIR="${SNAPSHOT_DIR:-/home/infra/dcim_metrics_project/rollback_snapshots}"
CONTAINER_NAME="${CONTAINER_NAME:-dcim-nifi}"
CONTAINER_PATH="${CONTAINER_PATH:-/home/infra/dcim_metrics_project/scripts/server_inventory_collector.py}"
COPY_TO_CONTAINER="${COPY_TO_CONTAINER:-false}"
RESTART_CONTAINER="${RESTART_CONTAINER:-false}"

# ---------- Validasi argumen ----------
if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <IP_ADDRESS>"
    echo "Contoh: $0 10.50.0.6"
    exit 1
fi

TARGET_IP="$1"

# Validasi format IP sederhana
if ! [[ "$TARGET_IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    echo "Error: '$TARGET_IP' bukan format IP address yang valid."
    exit 1
fi

if [[ ! -f "$TARGET_FILE" ]]; then
    echo "Error: File tidak ditemukan: $TARGET_FILE"
    exit 1
fi

# ---------- Cek apakah IP ada di file ----------
if ! grep -q "\"ip\": \"$TARGET_IP\"" "$TARGET_FILE"; then
    echo "IP $TARGET_IP tidak ditemukan di dalam REDFISH_SERVERS ($TARGET_FILE)."
    exit 1
fi

mkdir -p "$SNAPSHOT_DIR"
SNAPSHOT_FILE="$SNAPSHOT_DIR/server_inventory_${TARGET_IP//./_}.json"

# ---------- Backup file penuh (tetap dipertahankan, untuk audit) ----------
BACKUP_FILE="${TARGET_FILE}.bak.$(date +%Y%m%d%H%M%S)"
cp "$TARGET_FILE" "$BACKUP_FILE"
echo "Backup dibuat: $BACKUP_FILE"

# ---------- Simpan snapshot entry yang akan dihapus, lalu hapus ----------
python3 - "$TARGET_FILE" "$TARGET_IP" "$SNAPSHOT_FILE" <<'PYEOF'
import re
import sys
import json

target_file = sys.argv[1]
target_ip = sys.argv[2]
snapshot_file = sys.argv[3]

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

pattern = re.compile(r"(REDFISH_SERVERS\s*=\s*\[)(.*?)(\n\])", re.DOTALL)
match = pattern.search(content)

if not match:
    print("Error: Tidak menemukan blok REDFISH_SERVERS = [ ... ] di file.")
    sys.exit(1)

header, body, footer = match.groups()

entries = re.findall(r"\{[^{}]*\}", body)

new_entries = []
removed_entry_text = None
for entry in entries:
    if f'"{target_ip}"' in entry:
        removed_entry_text = entry
        continue
    new_entries.append(entry)

if removed_entry_text is None:
    print(f"IP {target_ip} tidak ditemukan saat parsing entry.")
    sys.exit(1)

# --- Simpan snapshot SEBELUM menulis file yang sudah diedit ---
with open(snapshot_file, "w", encoding="utf-8") as f:
    json.dump({
        "target_ip": target_ip,
        "target_file": target_file,
        "list_name": "REDFISH_SERVERS",
        "entry_text": removed_entry_text,
    }, f, indent=2)
print(f"Snapshot disimpan: {snapshot_file}")

new_body = "\n    " + ",\n    ".join(new_entries) if new_entries else ""
new_block = header + new_body + footer

new_content = content[:match.start()] + new_block + content[match.end():]

with open(target_file, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"Entry dengan IP {target_ip} berhasil dihapus dari {target_file}")
PYEOF

echo "Selesai mengedit file lokal: $TARGET_FILE"

# ---------- Opsional: copy ke dalam container ----------
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

echo "Selesai."
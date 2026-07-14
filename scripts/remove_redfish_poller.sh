#!/usr/bin/env bash
#
# remove-redfish-poller-server.sh
# Menghapus satu entry server (berdasarkan IP) dari list SERVERS
# di dalam redfish_poller.py, lalu (opsional) copy hasilnya ke container.
#
# Penggunaan:
#   ./remove-redfish-poller-server.sh <IP>
#
# Contoh:
#   ./remove-redfish-poller-server.sh 10.50.0.6
#
# Variabel yang bisa di-override lewat environment:
#   TARGET_FILE       Path file redfish_poller.py di host
#                      (default: /home/infra/dcim_metrics_project/scripts/redfish_poller.py)
#   CONTAINER_NAME     Nama container docker (default: dcim-nifi)
#   CONTAINER_PATH     Path file di dalam container
#                      (default: /home/infra/dcim_metrics_project/scripts/redfish_poller.py)
#   COPY_TO_CONTAINER  Set ke "true" untuk otomatis docker cp hasil edit ke container (default: false)
#   RESTART_CONTAINER  Set ke "true" untuk restart container setelah copy (default: false)

set -euo pipefail

# ---------- Konfigurasi default ----------
TARGET_FILE="${TARGET_FILE:-/home/infra/dcim_metrics_project/scripts/redfish_poller.py}"
CONTAINER_NAME="${CONTAINER_NAME:-dcim-nifi}"
CONTAINER_PATH="${CONTAINER_PATH:-/home/infra/dcim_metrics_project/scripts/redfish_poller.py}"
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
    echo "IP $TARGET_IP tidak ditemukan di dalam SERVERS ($TARGET_FILE)."
    exit 1
fi

# ---------- Backup sebelum edit ----------
BACKUP_FILE="${TARGET_FILE}.bak.$(date +%Y%m%d%H%M%S)"
cp "$TARGET_FILE" "$BACKUP_FILE"
echo "Backup dibuat: $BACKUP_FILE"

# ---------- Hapus entry menggunakan Python (parsing aman) ----------
python3 - "$TARGET_FILE" "$TARGET_IP" <<'PYEOF'
import re
import sys

target_file = sys.argv[1]
target_ip = sys.argv[2]

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

# Cari blok SERVERS = [ ... ]  (bukan REDFISH_SERVERS, dan bukan kata lain yang diakhiri "SERVERS")
pattern = re.compile(r"(?<![A-Za-z_])(SERVERS\s*=\s*\[)(.*?)(\n\])", re.DOTALL)
match = pattern.search(content)

if not match:
    print("Error: Tidak menemukan blok SERVERS = [ ... ] di file.")
    sys.exit(1)

header, body, footer = match.groups()

# Pecah tiap entry dict {...} di dalam list
entries = re.findall(r"\{[^{}]*\}", body)

new_entries = []
removed = False
for entry in entries:
    if f'"{target_ip}"' in entry:
        removed = True
        continue
    new_entries.append(entry)

if not removed:
    print(f"IP {target_ip} tidak ditemukan saat parsing entry.")
    sys.exit(1)

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

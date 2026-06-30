import shutil

md_file_path = '/home/infra/dcim_metrics_project/docs/development/34-database-query-baseline-for-agents.md'
backup_path = md_file_path + ".bak3"
shutil.copy(md_file_path, backup_path)

with open(md_file_path, 'r') as f:
    lines = f.readlines()

new_lines = []
in_sql_block = False
desc_buffer = []
is_header_active = False

def process_desc(buffer):
    text = "".join(buffer).strip()
    if not text:
        return ""
    if "**Fungsi Query**:" in text:
        return text + "\n\n"
        
    desc_parts = [
        "**Fungsi Query**:",
        text,
        "",
        "**Penjelasan Bagian Query**:",
        "- `SELECT`: Mengambil kolom yang relevan dari data.",
        "- `FROM / JOIN`: Menggabungkan tabel sumber data (seperti `dcim_events` dan `unified_assets`).",
        "- `WHERE`: Memfilter data berdasarkan waktu dan tipe/identitas perangkat.",
        "",
        "**Apa yang Perlu Diperhatikan**:",
        "- Pastikan parameter waktu (`NOW() - INTERVAL`) disesuaikan jika data dari collector terhambat.",
        "- Perhatikan potensi data `NULL` pada kolom identitas seperti `ip` jika perangkat tidak menyediakannya.",
        "- Hati-hati dengan nilai duplikat; gunakan `DISTINCT ON` jika hanya butuh identitas/snapshot terbaru."
    ]
    return "\n".join(desc_parts) + "\n\n"

i = 0
while i < len(lines):
    line = lines[i]
    if line.startswith('### ') or line.startswith('#### '):
        if desc_buffer:
            new_lines.append(process_desc(desc_buffer))
            desc_buffer = []
        new_lines.append(line)
        is_header_active = True
    elif line.startswith('```sql'):
        if is_header_active:
            if desc_buffer:
                new_lines.append(process_desc(desc_buffer))
                desc_buffer = []
            is_header_active = False
        new_lines.append(line)
        in_sql_block = True
    elif line.startswith('```') and in_sql_block:
        in_sql_block = False
        new_lines.append(line)
    elif in_sql_block:
        l_strip = line.strip()
        if l_strip.startswith('WHERE') and '--' not in line:
            new_lines.append(line.rstrip('\n') + "  -- Filter kondisi awal pencarian\n")
        elif l_strip.startswith('AND event_time >') and '--' not in line:
            new_lines.append(line.rstrip('\n') + "  -- Filter rentang waktu observasi\n")
        elif l_strip.startswith('AND device_type =') and '--' not in line:
            new_lines.append(line.rstrip('\n') + "  -- Filter spesifik tipe perangkat\n")
        elif l_strip.startswith('AND (') and 'OR ' in line and '--' not in line:
            new_lines.append(line.rstrip('\n') + "  -- Filter untuk multi-identitas perangkat\n")
        else:
            new_lines.append(line)
    elif is_header_active:
        if line.strip():
            desc_buffer.append(line)
        elif desc_buffer:
            desc_buffer.append(line)
    else:
        new_lines.append(line)
    i += 1

if desc_buffer:
    new_lines.append(process_desc(desc_buffer))

with open(md_file_path, 'w') as f:
    f.writelines(new_lines)

print("Documentation updated successfully.")

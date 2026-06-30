import re
import shutil

md_file_path = '/home/infra/dcim_metrics_project/docs/development/34-database-query-baseline-for-agents.md'
backup_path = md_file_path + ".bak2"
shutil.copy(md_file_path, backup_path)

with open(md_file_path, 'r') as f:
    content = f.read()

def process_section(match):
    header = match.group(1)
    desc = match.group(2).strip()
    sql = match.group(3)
    
    # Process description
    if "**Fungsi Query**:" not in desc:
        desc_parts = [
            "**Fungsi Query**:",
            desc,
            "",
            "**Penjelasan Bagian Query**:",
            "- `SELECT`: Mengambil kolom yang relevan dari data.",
            "- `FROM / JOIN`: Menggabungkan tabel sumber data (seperti dcim_events dan unified_assets).",
            "- `WHERE`: Memfilter data berdasarkan waktu (biasanya 24 jam terakhir) dan tipe/identitas perangkat.",
            "",
            "**Apa yang Perlu Diperhatikan**:",
            "- Pastikan parameter waktu (`NOW() - INTERVAL`) disesuaikan jika data agent terhambat.",
            "- Perhatikan potensi data `NULL` pada kolom identitas seperti `ip` jika perangkat tidak menyediakan IP (seperti UPS tertentu).",
            "- Hati-hati dengan nilai duplikat; gunakan `DISTINCT ON` jika hanya butuh data terbaru."
        ]
        new_desc = "\n".join(desc_parts)
    else:
        new_desc = desc
        
    # Process SQL comments on WHERE
    sql_lines = sql.split('\n')
    new_sql_lines = []
    for line in sql_lines:
        if line.strip().startswith('WHERE') and '--' not in line:
            new_sql_lines.append(line + "  -- Filter kondisi awal pencarian")
        elif line.strip().startswith('AND event_time >') and '--' not in line:
            new_sql_lines.append(line + "  -- Filter waktu (rentang observasi)")
        elif line.strip().startswith('AND device_type =') and '--' not in line:
            new_sql_lines.append(line + "  -- Filter spesifik tipe perangkat")
        elif line.strip().startswith('AND (') and 'OR' in sql and '--' not in line:
            new_sql_lines.append(line + "  -- Filter untuk multi-identitas perangkat (SN/Hostname/IP)")
        else:
            new_sql_lines.append(line)
            
    new_sql = "\n".join(new_sql_lines)
    
    return f"{header}\n\n{new_desc}\n\n```sql\n{new_sql}\n```"

# regex to find sections:
# ### (or ####) Title
# <description text>
# ```sql
# <sql text>
# ```
pattern = r'(#{3,4} [^\n]+)\n+(.*?)\n+```sql\n(.*?)\n```'

new_content = re.sub(pattern, process_section, content, flags=re.DOTALL)

with open(md_file_path, 'w') as f:
    f.write(new_content)

print("Documentation updated.")

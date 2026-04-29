import csv
import re
import os

def extract_reference_data(filepath):
    oid_map = {}
    name_map = {}
    
    if not os.path.exists(filepath):
        return oid_map, name_map
        
    with open(filepath, 'r') as f:
        lines = f.readlines()
        
    current_section = ""
    for line in lines:
        line = line.strip()
        if not line.startswith('|'):
            if line.startswith('##'): current_section = line.lower()
            continue
        if "quick reference" in current_section or "---" in line or "| status |" in line.lower():
            continue
        parts = [p.strip().strip('`') for p in line.split('|')]
        if len(parts) >= 6: 
            status, name, oid_val, unit_or_type, desc = parts[1:6]
            is_active = "TRUE" if "✅" in status else "FALSE"
            oid_clean = oid_val.lstrip('.')
            if re.match(r'^[\d\.]+$', oid_clean) and len(oid_clean.split('.')) >= 2:
                oid_map[oid_clean] = {'name': name, 'unit': unit_or_type, 'desc': desc, 'status': is_active}
                suffix = '.'.join(oid_clean.split('.')[-3:])
                if len(suffix.split('.')) >= 3: oid_map[suffix] = {'name': name, 'unit': unit_or_type, 'desc': desc, 'status': is_active}
            else:
                name_map[name.lower()] = {'name': name, 'unit': oid_val, 'desc': desc, 'status': is_active}
        elif len(parts) >= 5: 
            status, name, unit, desc = parts[1:5]
            is_active = "TRUE" if "✅" in status else "FALSE"
            name_map[name.lower()] = {'name': name, 'unit': unit, 'desc': desc, 'status': is_active}
                
    return oid_map, name_map

oid_map, name_map = extract_reference_data('/home/infra/dcim_metrics_project/docs/04-all-available-metrics.md')

def update_csv(filename, category):
    if not os.path.exists(filename): return
    rows = []
    with open(filename, 'r') as f:
        reader = csv.reader(f)
        try: headers = next(reader)
        except StopIteration: return
        
        status_col = headers.index('Status') if 'Status' in headers else -1
        desc_col = headers.index('Deskripsi') if 'Deskripsi' in headers else headers.index('Description') if 'Description' in headers else 4

        for row in reader:
            if not row: continue
            
            oid_col = 2
            raw_field = row[1].strip()
            raw_path_or_oid = row[oid_col].strip().lstrip('.').replace('iso.', '1.').replace('iso.3.6.1.4.1.318.1.1.1.', '').replace('3.6.1.4.1.318.1.1.1.', '')
            
            matched = None
            for k_oid, meta in oid_map.items():
                if raw_path_or_oid.endswith(k_oid) or k_oid.endswith(raw_path_or_oid):
                    matched = meta
                    break
            
            if not matched: 
                matched = name_map.get(raw_field.lower())

            if matched:
                row[1] = matched['name']
                row[desc_col] = matched['desc']
                if status_col != -1: row[status_col] = matched['status']
            else:
                # REVISION: Remove the Live Value from the Deskripsi column
                if "Value:" in row[desc_col]:
                    if raw_field.startswith('ifIn'): row[desc_col] = "Interface inbound traffic descriptor"
                    elif raw_field.startswith('ifOut'): row[desc_col] = "Interface outbound traffic descriptor"
                    elif 'Proxy' in category or 'camera' in category: row[desc_col] = "Direct camera ISAPI field"
                    else: row[desc_col] = "Technical parameter"
                
                # Clean up numeric field names
                if re.match(r'^[\d\.]+$', row[1]) or row[1].isdigit():
                    if '.' in row[2]: row[1] = row[2].split('.')[-1]
                
                # Fallback for empty strings
                if not row[desc_col]:
                    row[desc_col] = "System metric"

            rows.append(row)
            
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

base_dir = '/home/infra/dcim_metrics_project/docs/'
for cat in ['ups', 'mikrotik', 'server', 'nvr', 'cameras']:
    update_csv(base_dir + f'{cat}_metrics_exhaustive.csv', cat)

print("Exhaustive CSVs cleaned: Values removed, descriptions applied.")

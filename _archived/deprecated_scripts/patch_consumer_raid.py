import re

with open('/home/infra/dcim_metrics_project/scripts/dcim_itop_unified_consumer.py', 'r') as f:
    content = f.read()

old_vol = """            size_bytes = disk.get("capacity_bytes", 0)
            size_gb = int(size_bytes / (1024**3)) if size_bytes else 0
            description = f"{disk.get('media_type', 'Unknown')} - {disk.get('protocol', 'Unknown')} - {disk.get('model_name', 'Drive')}\""""

new_vol = """            size_bytes = disk.get("capacity_bytes", 0)
            size_gb = int(size_bytes / (1024**3)) if size_bytes else 0
            raid_level = disk.get("raid_level", "")
            raid_str = f"[{raid_level}] " if raid_level else ""
            description = f"{raid_str}{disk.get('media_type', 'Unknown')} - {disk.get('protocol', 'Unknown')} - {disk.get('model_name', 'Drive')}\""""

if old_vol in content:
    content = content.replace(old_vol, new_vol)
    with open('/home/infra/dcim_metrics_project/scripts/dcim_itop_unified_consumer.py', 'w') as f:
        f.write(content)
    print("Patched unified consumer successfully.")
else:
    print("Failed to find block in unified consumer")

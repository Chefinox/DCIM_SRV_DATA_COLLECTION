import re

with open('/home/infra/dcim_metrics_project/scripts/dcim_itop_unified_consumer.py', 'r') as f:
    content = f.read()

old_vol = """            size_bytes = disk.get("capacity_bytes", 0)
            size_gb = int(size_bytes / (1024**3)) if size_bytes else 0
            raid_level = disk.get("raid_level", "")"""

new_vol = """            # disk from postgres has 'size' directly in GiB, or fallback to capacity_bytes calculation
            size_gb = disk.get("size", 0)
            if not size_gb and disk.get("capacity_bytes"):
                size_gb = int(disk.get("capacity_bytes") / (1024**3))
                
            raid_level = disk.get("raid_level", "")"""

if old_vol in content:
    content = content.replace(old_vol, new_vol)
    with open('/home/infra/dcim_metrics_project/scripts/dcim_itop_unified_consumer.py', 'w') as f:
        f.write(content)
    print("Patched unified consumer size successfully.")
else:
    print("Failed to find block in unified consumer")

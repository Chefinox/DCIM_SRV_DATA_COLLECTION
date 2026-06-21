import re

with open('/home/infra/dcim_metrics_project/scripts/dcim_itop_unified_consumer.py', 'r') as f:
    content = f.read()

# I will find the methods that were injected at the top level and indent them properly,
# AND move them back inside the ITopClient class!

# Find where they are currently:
# They start with "    def get_network_interfaces(self, server_id):"
# and end right before "def sync_server_nics_and_disks"
# Actually, they already have 4 spaces indent!
# We just need to move them inside ITopClient class.
# ITopClient class ends at "        return False\n\n\n# ─── Redis Distributed Lock"
# But wait, `release_lock` is at the end of Redis block.

# Let's extract the methods block exactly:
start_str = "    def get_network_interfaces(self, server_id):"
end_str = "def sync_server_nics_and_disks(itop_client, server_id, hostname, org_id, location_id, hw_data):"

start_idx = content.find(start_str)
end_idx = content.find(end_str)

methods_block = content[start_idx:end_idx]

# Remove it from its current location
content = content[:start_idx] + content[end_idx:]

# Insert it at the end of ITopClient class
# Find the end of ITopClient
target_str = """        if body.get("code") == 0:
            return True
        else:
            logger.error(f"✗ iTop Update Error (ID={obj_id}): {body.get('message')}")
            return False"""

target_idx = content.find(target_str)
if target_idx != -1:
    insert_idx = target_idx + len(target_str)
    content = content[:insert_idx] + "\n\n" + methods_block + content[insert_idx:]

with open('/home/infra/dcim_metrics_project/scripts/dcim_itop_unified_consumer.py', 'w') as f:
    f.write(content)


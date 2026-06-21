import re

with open('/home/infra/dcim_metrics_project/scripts/server_inventory_to_pg.py', 'r') as f:
    content = f.read()

# We need to find the Storage section and modify it to also query Volumes.
old_storage_code = """    # 5. Disks
    storage_coll = get_redfish_data(f"{sys_url}/Storage", auth)
    if storage_coll:
        for controller in storage_coll.get("Members", []):
            c_data = get_redfish_data(f"https://{ip}{controller['@odata.id']}", auth)
            if c_data:
                for drive in c_data.get("Drives", []):
                    d = get_redfish_data(f"https://{ip}{drive['@odata.id']}", auth)
                    if d and d.get("SerialNumber") and d.get("Status", {}).get("State") != "Absent":
                        # Extract slot number
                        slot = d.get("Id")
                        phys_loc = d.get("PhysicalLocation", {})
                        part_loc = phys_loc.get("PartLocation", {})
                        if part_loc.get("LocationOrdinalValue") is not None:
                            slot = str(part_loc.get("LocationOrdinalValue"))
                        
                        inventory["disks"].append({
                            "model_name": d.get("Name") or d.get("Model"),
                            "serial_number": d.get("SerialNumber"),
                            "size": int(d.get("CapacityBytes", 0) / (1024**3)),  # Convert to GiB
                            "firmware_version": d.get("Revision"),
                            "slot": slot
                        })
        logging.info(f"  {ip}: Found {len(inventory['disks'])} disks")"""

new_storage_code = """    # 5. Disks & Volumes (RAID)
    storage_coll = get_redfish_data(f"{sys_url}/Storage", auth)
    if storage_coll:
        for controller in storage_coll.get("Members", []):
            c_data = get_redfish_data(f"https://{ip}{controller['@odata.id']}", auth)
            if c_data:
                # Build Drive to RAID mapping
                drive_raid_map = {}
                volumes_link = c_data.get("Volumes", {}).get("@odata.id")
                if volumes_link:
                    vols_data = get_redfish_data(f"https://{ip}{volumes_link}", auth)
                    if vols_data:
                        for vol_member in vols_data.get("Members", []):
                            vol = get_redfish_data(f"https://{ip}{vol_member['@odata.id']}", auth)
                            if vol:
                                raid_type = vol.get("RAIDType", "Unknown")
                                for drive_link in vol.get("Links", {}).get("Drives", []):
                                    drive_raid_map[drive_link.get("@odata.id")] = raid_type

                for drive in c_data.get("Drives", []):
                    drive_id = drive.get("@odata.id")
                    d = get_redfish_data(f"https://{ip}{drive_id}", auth)
                    if d and d.get("SerialNumber") and d.get("Status", {}).get("State") != "Absent":
                        # Extract slot number
                        slot = d.get("Id")
                        phys_loc = d.get("PhysicalLocation", {})
                        part_loc = phys_loc.get("PartLocation", {})
                        if part_loc.get("LocationOrdinalValue") is not None:
                            slot = str(part_loc.get("LocationOrdinalValue"))
                            
                        # Default to Non-RAID if not in a volume
                        raid_level = drive_raid_map.get(drive_id, "Non-RAID")
                        
                        inventory["disks"].append({
                            "model_name": d.get("Name") or d.get("Model"),
                            "serial_number": d.get("SerialNumber"),
                            "size": int(d.get("CapacityBytes", 0) / (1024**3)),  # Convert to GiB
                            "firmware_version": d.get("Revision"),
                            "slot": slot,
                            "raid_level": raid_level
                        })
        logging.info(f"  {ip}: Found {len(inventory['disks'])} disks")"""

if old_storage_code in content:
    content = content.replace(old_storage_code, new_storage_code)
    with open('/home/infra/dcim_metrics_project/scripts/server_inventory_to_pg.py', 'w') as f:
        f.write(content)
    print("Patched server_inventory_to_pg.py successfully.")
else:
    print("Could not find the target code block in server_inventory_to_pg.py.")


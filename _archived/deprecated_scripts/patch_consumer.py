import re

with open('/home/infra/dcim_metrics_project/scripts/dcim_itop_unified_consumer.py', 'r') as f:
    content = f.read()

# 1. Modify create_device signature and return
content = content.replace("def create_device(", "def create_device(")
content = content.replace(") -> bool:", ") -> str:")

create_return_old = """        if body.get("code") == 0:
            logger.info(f"✓ Auto-created {class_name} '{hostname}' (brand={brand_name}, serial={serial_number})")
            return True
        else:
            logger.error(f"✗ iTop Create Error for '{hostname}': {body.get('message')}")
            return False"""

create_return_new = """        if body.get("code") == 0:
            logger.info(f"✓ Auto-created {class_name} '{hostname}' (brand={brand_name}, serial={serial_number})")
            objs = body.get("objects", {})
            if objs:
                key = list(objs.keys())[0]
                return key.split("::")[1] if "::" in key else key
            return "created"
        else:
            logger.error(f"✗ iTop Create Error for '{hostname}': {body.get('message')}")
            return "" """
            
content = content.replace(create_return_old, create_return_new)


# 2. Add methods to ITopClient
methods_to_add = """
    def get_network_interfaces(self, server_id):
        body = self._post({
            "operation": "core/get",
            "class": "PhysicalInterface",
            "key": f"SELECT PhysicalInterface WHERE connectableci_id = '{server_id}'",
            "output_fields": "macaddress,name,speed,ipaddress"
        })
        return body.get("objects") or {}

    def create_network_interface(self, server_id, name, mac, speed_mbps, ip="", mask="", gateway=""):
        return self._post({
            "operation": "core/create",
            "class": "PhysicalInterface",
            "fields": {
                "connectableci_id": server_id,
                "name": name,
                "macaddress": mac,
                "speed": str(speed_mbps),
                "ipaddress": ip,
                "ipmask": mask,
                "ipgateway": gateway
            }
        })

    def update_network_interface(self, interface_id, name, speed_mbps, ip="", mask="", gateway=""):
        return self._post({
            "operation": "core/update",
            "class": "PhysicalInterface",
            "key": interface_id,
            "fields": {
                "name": name,
                "speed": str(speed_mbps),
                "ipaddress": ip,
                "ipmask": mask,
                "ipgateway": gateway
            }
        })

    def get_or_create_local_storage_system(self, hostname, org_id, location_id="0"):
        name = f"Local Storage - {hostname}"
        body = self._post({
            "operation": "core/get",
            "class": "StorageSystem",
            "key": f"SELECT StorageSystem WHERE name = '{name}'",
            "output_fields": "id,location_id"
        })
        objs = body.get("objects", {})
        if objs:
            key = list(objs.keys())[0]
            obj_id = key.split("::")[1] if "::" in key else key
            current_loc = objs[key]["fields"].get("location_id")
            if location_id != "0" and current_loc != location_id:
                self._post({
                    "operation": "core/update",
                    "class": "StorageSystem",
                    "key": obj_id,
                    "fields": {"location_id": location_id}
                })
            return obj_id
            
        res = self._post({
            "operation": "core/create",
            "class": "StorageSystem",
            "fields": {
                "name": name,
                "org_id": org_id,
                "location_id": location_id,
                "status": "production"
            }
        })
        objs = res.get("objects", {})
        if not objs: return "0"
        key = list(objs.keys())[0]
        return key.split("::")[1] if "::" in key else key

    def get_logical_volumes_for_storage(self, storage_id):
        body = self._post({
            "operation": "core/get",
            "class": "LogicalVolume",
            "key": f"SELECT LogicalVolume WHERE storagesystem_id = '{storage_id}'",
            "output_fields": "name,size,description"
        })
        return body.get("objects") or {}

    def create_logical_volume(self, storage_id, name, size_gb, description):
        res = self._post({
            "operation": "core/create",
            "class": "LogicalVolume",
            "fields": {
                "storagesystem_id": storage_id,
                "name": name,
                "size": str(size_gb),
                "description": description,
                "lun_id": name.split(" ")[-1] if " " in name else "0"
            }
        })
        objs = res.get("objects", {})
        if not objs: return "0"
        key = list(objs.keys())[0]
        return key.split("::")[1] if "::" in key else key
        
    def update_logical_volume(self, volume_id, size_gb, description):
        return self._post({
            "operation": "core/update",
            "class": "LogicalVolume",
            "key": volume_id,
            "fields": {
                "size": str(size_gb),
                "description": description
            }
        })

    def link_server_to_volume(self, server_id, volume_id, size_gb=0):
        body = self._post({
            "operation": "core/get",
            "class": "lnkServerToVolume",
            "key": f"SELECT lnkServerToVolume WHERE server_id='{server_id}' AND volume_id='{volume_id}'",
            "output_fields": "id,size_used"
        })
        objs = body.get("objects", {})
        if not objs:
            self._post({
                "operation": "core/create",
                "class": "lnkServerToVolume",
                "fields": {
                    "server_id": server_id,
                    "volume_id": volume_id,
                    "size_used": str(size_gb)
                }
            })
            logger.info(f"    ↳ Created Link ServerToVolume: size_used={size_gb}")
        else:
            key = list(objs.keys())[0]
            obj_id = key.split("::")[1] if "::" in key else key
            current_size = objs[key]["fields"].get("size_used", "0")
            if str(current_size) != str(size_gb):
                self._post({
                    "operation": "core/update",
                    "class": "lnkServerToVolume",
                    "key": obj_id,
                    "fields": {
                        "size_used": str(size_gb)
                    }
                })
                logger.info(f"    ↳ Updated Link ServerToVolume: size_used={current_size} -> {size_gb}")
"""

# Insert methods before "def process_message"
content = content.replace("def process_message(", methods_to_add + "\n\ndef process_message(")


# 3. Add sync logic function
sync_logic_func = """
def sync_server_nics_and_disks(itop_client, server_id, hostname, org_id, location_id, hw_data):
    if not hw_data:
        return
        
    # 1. Sync NICs
    nic_comps = hw_data.get("nic_comps", [])
    if nic_comps:
        speed_map_mbps = {1: 10, 2: 100, 3: 1000, 4: 10000, 5: 40000, 6: 100000, 7: 25000}
        existing_nics = itop_client.get_network_interfaces(server_id)
        existing_macs = {v['fields'].get('macaddress', '').lower(): k for k, v in existing_nics.items()}
        
        for nic in nic_comps:
            mac = (nic.get("mac") or "").strip().lower()
            if not mac:
                continue
                
            label = nic.get("label", "NIC")
            speed_enum = nic.get("speed", 11)
            speed_mbps = speed_map_mbps.get(speed_enum, 0)
            ip = nic.get("ip_address", "")
            mask = nic.get("ip_mask", "")
            gateway = nic.get("ip_gateway", "")
            
            if mac in existing_macs:
                nic_id = existing_macs[mac]
                nic_data = next((v['fields'] for k, v in existing_nics.items() if (k.split("::")[1] if "::" in k else k) == nic_id.split("::")[-1]), {})
                if str(nic_data.get("speed")) != f"{speed_mbps}.00" or nic_data.get("ipaddress") != ip:
                    logger.info(f"  -> Updating NIC {label} for {hostname}")
                    itop_client.update_network_interface(nic_id.split("::")[-1] if "::" in nic_id else nic_id, label, speed_mbps, ip, mask, gateway)
            else:
                logger.info(f"  -> Creating NIC {label} ({mac}) for {hostname}")
                itop_client.create_network_interface(server_id, label, mac, speed_mbps, ip, mask, gateway)
                
    # 2. Sync Logical Volumes (Disks)
    disk_comps = hw_data.get("disk_comps", [])
    if disk_comps:
        storage_id = itop_client.get_or_create_local_storage_system(hostname, org_id, location_id)
        existing_vols = itop_client.get_logical_volumes_for_storage(storage_id)
        existing_vol_names = {v['fields'].get('name', ''): k.split("::")[1] if "::" in k else k for k, v in existing_vols.items()}
        
        for disk in disk_comps:
            slot = disk.get("slot", "")
            slot_str = str(slot).zfill(2) if str(slot).isdigit() else slot
            name = f"Slot {slot_str}" if slot else disk.get("model_name", "Drive")
            
            size_bytes = disk.get("capacity_bytes", 0)
            size_gb = int(size_bytes / (1024**3)) if size_bytes else 0
            description = f"{disk.get('media_type', 'Unknown')} - {disk.get('protocol', 'Unknown')} - {disk.get('model_name', 'Drive')}"
            
            if name in existing_vol_names:
                vol_id = existing_vol_names[name]
                vol_data = next((v['fields'] for k, v in existing_vols.items() if (k.split("::")[1] if "::" in k else k) == vol_id), {})
                if str(vol_data.get("size")) != str(size_gb) or vol_data.get("description") != description:
                    itop_client.update_logical_volume(vol_id, size_gb, description)
            else:
                logger.info(f"  -> Creating Logical Volume {name} for {hostname}")
                vol_id = itop_client.create_logical_volume(storage_id, name, size_gb, description)
                
            # Link ke server
            itop_client.link_server_to_volume(server_id, vol_id, size_gb)

"""

content = content.replace("def process_message(", sync_logic_func + "\ndef process_message(")


# 4. Inject call in create path
create_old = """            created = itop_client.create_device(
                device_type    = device_type,
                hostname       = ci_name,
                ip             = ip,
                expected_status= expected_status,
                org_id         = auto_org_id,
                brand_name     = brand_name,
                model_name     = model_name,
                serial_number  = serial_number,
                extra_fields   = extra_fields
            )
            if created:
                r_cache.hset(cache_key, mapping={"""

create_new = """            created_id = itop_client.create_device(
                device_type    = device_type,
                hostname       = ci_name,
                ip             = ip,
                expected_status= expected_status,
                org_id         = auto_org_id,
                brand_name     = brand_name,
                model_name     = model_name,
                serial_number  = serial_number,
                extra_fields   = extra_fields
            )
            if created_id:
                # Sinkronisasi NIC & Logical Volumes jika Server
                if resolved_class == "Server" and hw and created_id != "created":
                    loc = extra_fields.get("location_id", "0")
                    sync_server_nics_and_disks(itop_client, created_id, ci_name, auto_org_id, loc, hw)
                
                r_cache.hset(cache_key, mapping={"""

content = content.replace(create_old, create_new)


# 5. Inject call in update path
update_old = """    # Auto-fill missing hardware fields for Server
    if class_name == "Server":
        hw = get_server_hardware(ci_name)
        if hw:
            if hw.get("cpu") and not obj_fields.get("cpu"): fields_to_update["cpu"] = hw["cpu"]
            if hw.get("ram") and not obj_fields.get("ram"): fields_to_update["ram"] = hw["ram"]
            if hw.get("nb_u") and not obj_fields.get("nb_u"): fields_to_update["nb_u"] = hw.get("nb_u", "2")
            if hw.get("site") and (not obj_fields.get("location_id") or obj_fields.get("location_id") == "0"):
                loc_id = itop_client.get_or_create_location(hw["site"], auto_org_id)
                if loc_id != "0":
                    fields_to_update["location_id"] = loc_id
                    if hw.get("rack") and (not obj_fields.get("rack_id") or obj_fields.get("rack_id") == "0"):
                        rack_id = itop_client.get_or_create_rack(hw["rack"], loc_id, auto_org_id)
                        if rack_id != "0":
                            fields_to_update["rack_id"] = rack_id

    if not fields_to_update:"""

update_new = """    # Auto-fill missing hardware fields for Server
    if class_name == "Server":
        hw = get_server_hardware(ci_name)
        if hw:
            if hw.get("cpu") and not obj_fields.get("cpu"): fields_to_update["cpu"] = hw["cpu"]
            if hw.get("ram") and not obj_fields.get("ram"): fields_to_update["ram"] = hw["ram"]
            if hw.get("nb_u") and not obj_fields.get("nb_u"): fields_to_update["nb_u"] = hw.get("nb_u", "2")
            if hw.get("site") and (not obj_fields.get("location_id") or obj_fields.get("location_id") == "0"):
                loc_id = itop_client.get_or_create_location(hw["site"], auto_org_id)
                if loc_id != "0":
                    fields_to_update["location_id"] = loc_id
                    if hw.get("rack") and (not obj_fields.get("rack_id") or obj_fields.get("rack_id") == "0"):
                        rack_id = itop_client.get_or_create_rack(hw["rack"], loc_id, auto_org_id)
                        if rack_id != "0":
                            fields_to_update["rack_id"] = rack_id
                            
            # Selalu sync NIC dan Disk jika data HW ada
            loc = fields_to_update.get("location_id", obj_fields.get("location_id", "0"))
            sync_server_nics_and_disks(itop_client, obj_id, ci_name, auto_org_id, loc, hw)

    if not fields_to_update:"""

content = content.replace(update_old, update_new)

with open('/home/infra/dcim_metrics_project/scripts/dcim_itop_unified_consumer.py', 'w') as f:
    f.write(content)


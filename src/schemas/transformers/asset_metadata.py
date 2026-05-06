from datetime import datetime

def extract_metadata(row):
    """
    Pure transformer: Extract rich metadata from unified_assets row.
    Expects row: (hostname, sn, site, raw_json_dict)
    
    Robustness improvements:
    - Checks for None raw payloads
    - Safe nested dict access
    - Vendor-specific logic separation (logic only, no I/O)
    """
    if not row or len(row) < 4:
        return {}

    sql_hostname, sql_sn, sql_site, raw = row
    
    # Robustness: ensure raw is a dict
    if raw is None:
        raw = {}
    elif not isinstance(raw, dict):
        raw = {}

    # Clean SQL SN
    clean_sn = str(sql_sn).strip() if sql_sn else None
    if clean_sn in ["NO_SN", "Unknown", "", "None"]:
        clean_sn = None

    meta = {
        "serial_number": clean_sn or sql_sn,
        "hostname": sql_hostname,
        "site": sql_site or "FIT-Head-Office",
        "rack_name": "Unknown",
        "rack_position": None,
        "room_name": "Unknown",
        "manufacturer": "Unknown",
        "model": "Unknown",
        "asset_status": "Unknown",
        "environment": "Production",
        "business_unit": "Unknown",
        "enrichment_status": "PARTIAL",
        "last_modified_cmdb": None,
        "cached_at": datetime.utcnow().isoformat()
    }

    if not raw:
        return meta

    # Vendor Detection based on API URL signatures
    url = raw.get("url", "")
    if not isinstance(url, str): url = ""
    
    is_netbox = "/api/dcim/" in url
    is_ralph  = "/api/data-center-assets/" in url

    if is_netbox:
        if not clean_sn:
            meta["serial_number"] = raw.get("serial") or meta["serial_number"]
        
        meta["rack_name"]     = raw.get("rack", {}).get("name", "Unknown") if isinstance(raw.get("rack"), dict) else "Unknown"
        meta["rack_position"] = raw.get("position")
        meta["asset_status"]  = raw.get("status", {}).get("value", "Active") if isinstance(raw.get("status"), dict) else "Active"
        meta["business_unit"] = raw.get("tenant", {}).get("name", "Unknown") if isinstance(raw.get("tenant"), dict) else "Unknown"
        
        dev_type = raw.get("device_type", {}) if isinstance(raw.get("device_type"), dict) else {}
        meta["manufacturer"]  = dev_type.get("manufacturer", {}).get("name", "Unknown") if isinstance(dev_type.get("manufacturer"), dict) else "Unknown"
        meta["model"]         = dev_type.get("model", "Unknown") if isinstance(dev_type, dict) else "Unknown"
        meta["last_modified_cmdb"] = raw.get("last_updated")
        
    elif is_ralph:
        if not clean_sn:
            meta["serial_number"] = raw.get("sn") or meta["serial_number"]

        rack_data = raw.get("rack", {}) if isinstance(raw.get("rack"), dict) else {}
        meta["rack_name"]     = rack_data.get("name", "Unknown")
        meta["room_name"]     = rack_data.get("server_room", {}).get("name", "Unknown") if isinstance(rack_data.get("server_room"), dict) else "Unknown"
        meta["rack_position"] = raw.get("position")
        meta["asset_status"]  = raw.get("status", "Unknown")
        meta["business_unit"] = raw.get("property_of", {}).get("name", "Unknown") if isinstance(raw.get("property_of"), dict) else "Unknown"
        meta["environment"]   = raw.get("service_env", {}).get("name", "Production") if isinstance(raw.get("service_env"), dict) else "Production"
        
        model_data = raw.get("model", {}) if isinstance(raw.get("model"), dict) else {}
        meta["manufacturer"]  = model_data.get("manufacturer", {}).get("name", "Unknown") if isinstance(model_data.get("manufacturer"), dict) else "Unknown"
        meta["model"]         = model_data.get("name", "Unknown")
        meta["last_modified_cmdb"] = raw.get("modified")

    # Final validation for FULL status
    if meta["serial_number"] and meta["site"] and meta.get("rack_name") != "Unknown":
        meta["enrichment_status"] = "FULL"
    
    return meta

from datetime import datetime

def extract_metadata(row):
    """
    Pure transformer: Extract rich metadata from unified_assets row.
    Supports both legacy JSONB-based rows and new flat schema rows.
    """
    if not row:
        return {}

    # Initial mapping for flat schema (10 columns)
    # (hostname, sn, site, manufacturer, model, rack_name, rack_position, status, bu, env)
    if len(row) >= 10:
        sql_hostname, sql_sn, sql_site, sql_manu, sql_model, sql_rack, sql_pos, sql_status, sql_bu, sql_env = row[:10]
        meta = {
            "serial_number": sql_sn,
            "hostname": sql_hostname,
            "site": sql_site or "Local Instance",
            "rack_name": sql_rack or "Unknown",
            "rack_position": sql_pos,
            "manufacturer": sql_manu or "Unknown",
            "model": sql_model or "Unknown",
            "asset_status": sql_status or "in use",
            "business_unit": sql_bu or "IT Infrastructure Departement",
            "environment": sql_env or "Production",
            "enrichment_status": "PARTIAL",
            "cached_at": datetime.utcnow().isoformat()
        }
        if meta["serial_number"] and meta["site"] and meta["rack_name"] != "Unknown":
            meta["enrichment_status"] = "FULL"
        return meta

    # Legacy / Mixed Path
    if len(row) < 4:
        return {}

    sql_hostname, sql_sn, sql_site, raw = row[:4]
    
    if raw is None or not isinstance(raw, dict):
        raw = {}

    meta = {
        "serial_number": sql_sn,
        "hostname": sql_hostname,
        "site": sql_site or "Local Instance",
        "rack_name": "Unknown",
        "rack_position": None,
        "manufacturer": "Unknown",
        "model": "Unknown",
        "asset_status": "Unknown",
        "environment": "Production",
        "business_unit": "Unknown",
        "enrichment_status": "PARTIAL",
        "cached_at": datetime.utcnow().isoformat()
    }

    if not raw:
        return meta

    # Ralph / NetBox JSON Logic
    url = raw.get("url", "")
    is_netbox = "/api/dcim/" in str(url)
    is_ralph  = "/api/data-center-assets/" in str(url)

    if is_netbox:
        meta["rack_name"]     = raw.get("rack", {}).get("name", "Unknown") if isinstance(raw.get("rack"), dict) else "Unknown"
        meta["manufacturer"]  = raw.get("device_type", {}).get("manufacturer", {}).get("name", "Unknown") if isinstance(raw.get("device_type"), dict) else "Unknown"
        meta["model"]         = raw.get("device_type", {}).get("model", "Unknown") if isinstance(raw.get("device_type"), dict) else "Unknown"
    elif is_ralph:
        rack_data = raw.get("rack", {}) if isinstance(raw.get("rack"), dict) else {}
        meta["rack_name"]     = rack_data.get("name", "Unknown")
        model_data = raw.get("model", {}) if isinstance(raw.get("model"), dict) else {}
        meta["manufacturer"]  = model_data.get("manufacturer", {}).get("name", "Unknown") if isinstance(model_data, dict) else "Unknown"
        meta["model"]         = model_data.get("name", "Unknown")

    if meta["serial_number"] and meta["site"] and meta["rack_name"] != "Unknown":
        meta["enrichment_status"] = "FULL"
    
    return meta

import logging
from src.tools.protocols.hikvision_client import HikvisionClient
from src.schemas.transformers.cctv_metadata import parse_isapi_xml, transform_to_cctv_metrics

class CCTVPollerExecutor:
    """
    SINGLE RESPONSIBILITY:
    - Poll status and metadata from a single Hikvision device.
    - Transform result into standardized schema.
    """
    def __init__(self):
        pass

    def poll_device(self, ip, user, password, device_category="CCTV"):
        logging.info(f"Capability: CCTV Polling -> {ip}")
        client = HikvisionClient(ip, user, password)
        
        # 1. Fetch Info
        info_xml = client.get_isapi("/System/deviceInfo")
        if not info_xml:
            return self._offline_state(ip, device_category)

        # 2. Parse & Transform
        device_info = parse_isapi_xml(info_xml)
        
        # 3. Optional Status Fetch
        status_xml = client.get_isapi("/System/status")
        sys_status = parse_isapi_xml(status_xml) if status_xml else None
        
        metrics = transform_to_cctv_metrics(ip, device_info, sys_status)
        metrics["device_category"] = device_category
        return metrics

    def discover_nvr_channels(self, nvr_ip, user, password):
        """
        Capability: NVR Proxy Discovery.
        Returns a mapping of {camera_ip: {serial_number, model, firmware, hostname}}.
        """
        client = HikvisionClient(nvr_ip, user, password)
        xml_data = client.get_isapi("/ContentMgmt/InputProxy/channels")
        if not xml_data:
            return {}
        
        # Use simple parsing for channel discovery
        mapping = {}
        channels = parse_isapi_xml(xml_data).get("InputProxyChannel", [])
        if isinstance(channels, dict): channels = [channels] # Handle single item
        
        for ch in channels:
            desc = ch.get("sourceInputPortDescriptor") or {}
            ip = desc.get("ipAddress")
            sn = desc.get("serialNumber")
            model = desc.get("model")
            fw = desc.get("firmwareVersion")
            name = ch.get("name")
            if ip and sn:
                mapping[ip] = {
                    "serial_number": sn,
                    "model": model,
                    "firmware": fw,
                    "hostname": name
                }
        return mapping

    def _offline_state(self, ip, category):
        return {
            "ip": ip,
            "status": "Offline",
            "device_category": category,
            "hostname": f"CCTV-{str(ip).replace('.', '-')}",
            "serial_number": f"CCTV-IP-{str(ip).replace('.', '-')}",
            "manufacturer": "Hikvision",
            "model": "DS-2CD",
            "device_type": "cctv"
        }

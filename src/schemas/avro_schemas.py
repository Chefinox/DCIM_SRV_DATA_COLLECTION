NORMALIZED_EVENT_SCHEMA = """
{
  "type": "record",
  "name": "NormalizedEvent",
  "namespace": "dcim.events",
  "fields": [
    {"name": "event_id", "type": "string"},
    {"name": "event_time", "type": ["null", "string"], "default": null},
    {"name": "timestamp", "type": ["null", "long", "string", "double"], "default": null},
    {"name": "source_topic", "type": "string"},
    {"name": "measurement", "type": ["null", "string"], "default": null},
    {"name": "device_type", "type": "string"},
    {"name": "hostname", "type": "string"},
    {"name": "ip", "type": ["null", "string"], "default": null},
    {"name": "serial_number", "type": ["null", "string"], "default": null},
    {"name": "metric_name", "type": "string"},
    {"name": "metric_value", "type": ["null", "double", "int", "string"], "default": null},
    {"name": "metric_unit", "type": ["null", "string"], "default": null},
    {"name": "severity", "type": ["null", "string"], "default": null},
    {"name": "manufacturer", "type": ["null", "string"], "default": null},
    {"name": "model", "type": ["null", "string"], "default": null},
    {"name": "firmware", "type": ["null", "string"], "default": null},
    {"name": "raw_fields", "type": ["null", "string"], "default": null},
    {"name": "raw_tags", "type": ["null", "string"], "default": null}
  ]
}
"""

ENRICHED_EVENT_SCHEMA = """
{
  "type": "record",
  "name": "EnrichedEvent",
  "namespace": "dcim.events",
  "fields": [
    {"name": "event_id", "type": "string"},
    {"name": "event_time", "type": ["null", "string"], "default": null},
    {"name": "timestamp", "type": ["null", "long", "string", "double"], "default": null},
    {"name": "source_topic", "type": "string"},
    {"name": "measurement", "type": ["null", "string"], "default": null},
    {"name": "device_type", "type": "string"},
    {"name": "hostname", "type": "string"},
    {"name": "ip", "type": ["null", "string"], "default": null},
    {"name": "serial_number", "type": ["null", "string"], "default": null},
    {"name": "metric_name", "type": "string"},
    {"name": "metric_value", "type": ["null", "double", "int", "string"], "default": null},
    {"name": "metric_unit", "type": ["null", "string"], "default": null},
    {"name": "severity", "type": ["null", "string"], "default": null},
    {"name": "manufacturer", "type": ["null", "string"], "default": null},
    {"name": "model", "type": ["null", "string"], "default": null},
    {"name": "firmware", "type": ["null", "string"], "default": null},
    {"name": "raw_fields", "type": ["null", "string"], "default": null},
    {"name": "raw_tags", "type": ["null", "string"], "default": null},
    {"name": "site_id", "type": ["null", "string"], "default": null},
    {"name": "rack_id", "type": ["null", "string"], "default": null},
    {"name": "tenant", "type": ["null", "string"], "default": null},
    {"name": "status", "type": ["null", "string"], "default": null},
    {"name": "asset_tag", "type": ["null", "string"], "default": null},
    {"name": "owner", "type": ["null", "string"], "default": null},
    {"name": "department", "type": ["null", "string"], "default": null},
    {"name": "cmdb_sync_time", "type": ["null", "string"], "default": null},
    {"name": "ci_id", "type": ["null", "string"], "default": null},
    {"name": "asset_id", "type": ["null", "string"], "default": null}
  ]
}
"""

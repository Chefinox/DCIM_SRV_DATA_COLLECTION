import sys
import json
import requests

sys.path.append("/home/infra/dcim_metrics_project")
from src.schemas.avro_schemas import ENRICHED_EVENT_SCHEMA

registry_url = "http://10.70.0.56:8081/subjects/dcim.events.EnrichedEvent/versions"

payload = {
    "schema": ENRICHED_EVENT_SCHEMA
}

try:
    response = requests.post(
        registry_url,
        headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
        json=payload
    )
    response.raise_for_status()
    print("Schema registered successfully:")
    print(response.json())
except Exception as e:
    print(f"Failed to register schema: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(e.response.text)

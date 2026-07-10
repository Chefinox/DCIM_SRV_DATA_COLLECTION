import json
import requests
from src.schemas.avro_schemas import ENRICHED_EVENT_SCHEMA

payload = {
    "schema": ENRICHED_EVENT_SCHEMA,
    "schemaType": "AVRO"
}

res = requests.post(
    "http://localhost:8081/subjects/dcim.enriched.events-value/versions",
    headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
    data=json.dumps(payload)
)
print(res.status_code, res.text)

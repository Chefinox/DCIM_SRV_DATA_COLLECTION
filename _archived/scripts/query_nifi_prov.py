import requests
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Start a provenance query
req_body = {
    "provenance": {
        "request": {
            "maxResults": 5,
            "searchTerms": {
                "ProcessorID": "126cb21e-019f-1000-fdd4-29944c3770e1" # wait, I don't know the processor ID of GetSNMP. Let me just get recent events.
            }
        }
    }
}
# Actually it's easier to use NiFi API /nifi-api/provenance to submit a query, but we don't have the component ID of GetSNMP easily accessible without checking nifi_flow.json.

# Enrichment Status Fix - PARTIAL to FULL

## 🔍 Problem

Dashboard menampilkan **100% PARTIAL** enrichment status padahal CMDB data tersedia di Redis.

## 🐛 Root Cause

**Redis Key Mismatch**:
- Redis sync service menyimpan dengan key: `asset:sn:{serial_number}`
- Enrichment service mencari dengan key: `asset:{serial_number}`
- **Prefix `sn:` tidak match!**

Example:
```
Redis key:        asset:sn:j901gkxx
Enrichment lookup: asset:j901gkxx
Result: NOT FOUND → PARTIAL enrichment
```

## ✅ Solution

Updated enrichment service (`src/skills/inventory/enrichment/executor.py`) to try both key formats:

```python
# Try with sn: prefix first (primary lookup)
data_str = redis_client.get(f"asset:sn:{ident_clean.lower()}")
data = json.loads(data_str) if data_str else None

# Fallback to old format without sn: prefix
if not data:
    data_str = redis_client.get(f"asset:{ident_clean.lower()}")
    data = json.loads(data_str) if data_str else None

# SQL fallback if still not found
if not data:
    data = lookup_sql_fallback(ident_clean)
```

## 🚀 Applied Fix

### 1. Updated Code
```bash
# File: src/skills/inventory/enrichment/executor.py
# Line: ~82
# Changed: asset:{ident} → asset:sn:{ident} with fallback
```

### 2. Restarted Service
```bash
# Kill old process
sudo lsof -ti:8000 | xargs -r sudo kill -9

# Start in screen session
cd /home/infra/dcim_metrics_project
screen -dmS enrichment python3 -m uvicorn \
  src.skills.inventory.enrichment.executor:app \
  --host 0.0.0.0 --port 8000
```

### 3. Verified Fix
```bash
curl -s http://localhost:8000/enrich/J901GKXY | jq '.'
```

**Before Fix**:
```json
{
  "enrichment_status": "NOT_IN_CMDB",
  "site": "Unknown",
  "rack_name": "Unknown"
}
```

**After Fix**:
```json
{
  "enrichment_status": "FULL",
  "site": "FIT-Head-Office",
  "rack_name": "Rack Server 2",
  "manufacturer": "Lenovo",
  "model": "ThinkSystem SR650 V3"
}
```

## 📊 Impact

### Before Fix
- **100% PARTIAL** enrichment
- Missing: site, rack_name, manufacturer, model
- Only had: hostname, IP, serial_number

### After Fix
- **FULL enrichment** for devices in CMDB (68 assets)
- Complete metadata: site, rack, manufacturer, model
- Better dashboard insights

## ⏱️ Timeline

- **Data already in Elasticsearch**: Still shows PARTIAL (historical data)
- **New data (after fix)**: Will show FULL enrichment
- **Wait time**: 1-5 minutes for new metrics to arrive

## 🔍 Verification

### Check Current Enrichment Status
```bash
curl -k -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' \
  'https://10.70.0.56:9200/dcim-metrics-unified-*/_search' \
  -H 'Content-Type: application/json' \
  -d '{
    "size": 0,
    "query": {"range": {"@timestamp": {"gte": "now-5m"}}},
    "aggs": {
      "enrichment": {"terms": {"field": "enrichment_status.keyword"}},
      "by_device": {
        "terms": {"field": "device_type.keyword"},
        "aggs": {"enrichment": {"terms": {"field": "enrichment_status.keyword"}}}
      }
    }
  }' | jq '.aggregations'
```

### Check Specific Device
```bash
# Test enrichment API
curl -s http://localhost:8000/enrich/J901GKXY | jq '.enrichment_status'

# Check in Elasticsearch
curl -k -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' \
  'https://10.70.0.56:9200/dcim-metrics-unified-*/_search' \
  -H 'Content-Type: application/json' \
  -d '{
    "size": 1,
    "query": {
      "bool": {
        "must": [
          {"term": {"serial_number.keyword": "J901GKXY"}},
          {"range": {"@timestamp": {"gte": "now-5m"}}}
        ]
      }
    },
    "_source": ["enrichment_status", "site", "rack_name", "manufacturer", "model"]
  }' | jq '.hits.hits[0]._source'
```

### Check Redis Data
```bash
# List all asset keys
redis-cli -h 10.70.0.56 -p 6379 KEYS "asset:sn:*" | wc -l

# Get specific asset
redis-cli -h 10.70.0.56 -p 6379 GET "asset:sn:j901gkxx" | jq '.'
```

## 📈 Expected Results

After fix is applied and new data arrives:

| Device Type | CMDB Assets | Expected Status |
|-------------|-------------|-----------------|
| Server | ~20 devices | FULL |
| Network Switch | ~15 devices | FULL |
| CCTV | ~30 devices | PARTIAL (not in CMDB) |
| NAS | ~3 devices | FULL |
| NVR | ~2 devices | FULL |

**Note**: CCTV cameras typically not registered in CMDB, so PARTIAL is expected.

## 🔧 Maintenance

### Restart Enrichment Service
```bash
# Check if running
ps aux | grep "enrichment/executor"

# Kill if needed
sudo lsof -ti:8000 | xargs -r sudo kill -9

# Start in screen
cd /home/infra/dcim_metrics_project
screen -dmS enrichment python3 -m uvicorn \
  src.skills.inventory.enrichment.executor:app \
  --host 0.0.0.0 --port 8000

# Verify
curl -s http://localhost:8000/health 2>/dev/null || echo "Service not responding"
```

### Monitor Enrichment
```bash
# Watch enrichment status in real-time
watch -n 5 'curl -k -s -u elastic:"C+H+pFb*aIAqWcOo-X8q" \
  "https://10.70.0.56:9200/dcim-metrics-unified-*/_search" \
  -H "Content-Type: application/json" \
  -d "{\"size\":0,\"query\":{\"range\":{\"@timestamp\":{\"gte\":\"now-5m\"}}},\"aggs\":{\"enrichment\":{\"terms\":{\"field\":\"enrichment_status.keyword\"}}}}" \
  | jq ".aggregations.enrichment.buckets"'
```

## 📝 Related Files

- **Enrichment Service**: `src/skills/inventory/enrichment/executor.py`
- **Redis Sync**: `src/skills/inventory/redis_sync/executor.py`
- **Kafka Consumer**: `scripts/kafka_to_es_sync.py`

## ✅ Checklist

- [x] Identified root cause (Redis key mismatch)
- [x] Updated enrichment service code
- [x] Restarted enrichment service
- [x] Verified fix with test API call
- [ ] Wait for new data to arrive (1-5 minutes)
- [ ] Verify dashboard shows FULL enrichment
- [ ] Monitor for 24 hours to ensure stability

---

**Fixed**: 2026-05-12 21:30  
**Status**: ✅ Applied, waiting for new data  
**Impact**: High - Improves data quality for monitoring

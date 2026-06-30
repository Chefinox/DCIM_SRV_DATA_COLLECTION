# Dashboard Fix Summary - May 13, 2026

## 🐛 Issues Reported

1. **Enrichment Status 100% PARTIAL**
2. **Server Details "No results found"**

---

## ✅ Root Causes & Fixes

### Issue 1: Enrichment Status PARTIAL

**Root Cause**:
- PostgreSQL CMDB database (192.168.101.73:5432) **not accessible**
- Connection timeout error in redis_sync service
- Redis cache expired (TTL 300 seconds = 5 minutes)
- No CMDB data available for enrichment

**Error Log**:
```
2026-05-13 08:28:51 - ERROR - Error during sync: connection to server at "192.168.101.73", port 5432 failed: Connection timed out
```

**Temporary Fix Applied**:
1. Created `scripts/populate_redis_minimal.py`
2. Populated Redis with minimal CMDB data for known devices
3. Set TTL to 3600 seconds (1 hour)
4. Verified enrichment service returns FULL status

**Results**:
```bash
# Before
curl http://localhost:8000/enrich/J901GKXY
{"enrichment_status": "NOT_IN_CMDB", "site": "Unknown"}

# After
curl http://localhost:8000/enrich/J901GKXY
{"enrichment_status": "FULL", "site": "FIT-Head-Office", "rack_name": "Rack Server 2"}
```

**Devices Populated**:
- 35 devices from Elasticsearch (last 24h)
- 8 known devices from static list
- Total: 43 devices in Redis cache

**Permanent Fix Required**:
- Restore PostgreSQL database connectivity
- Check firewall rules for port 5432
- Or migrate CMDB to local database

---

### Issue 2: Server Details "No results found"

**Root Cause**:
- Index pattern `dcim-metrics-*` created **without field mappings**
- Kibana cannot render visualizations without field definitions
- Same issue as previous `dcim-working` index pattern

**Fix Applied**:
1. Created `scripts/fix_dashboard_index_pattern.py`
2. Fetched 583 field mappings from Elasticsearch
3. Recreated index pattern with complete field definitions

**Results**:
```
✅ Index Pattern ID: dcim-metrics-*
✅ Pattern: dcim-metrics-unified-*
✅ Fields: 583
```

**Verification**:
```bash
# Check data exists
curl -k -s -u elastic:'...' 'https://10.70.0.56:9200/dcim-metrics-unified-*/_search' \
  -d '{"size":0,"query":{"term":{"device_type.keyword":"server"}},"aggs":{"servers":{"terms":{"field":"hostname.keyword"}}}}' \
  | jq '.aggregations.servers.buckets | length'
# Output: 5 servers found
```

---

## 📊 Current Status

### Dashboard
- ✅ URL: http://10.70.0.56:5601/app/dashboards#/view/dcim-monitoring
- ✅ Index pattern fixed with 583 fields
- ✅ All visualizations should now display data
- ✅ Server Details table should show results

### Enrichment
- ✅ Service running on port 8000
- ✅ Redis populated with 43 devices
- ⚠️ Temporary data (1-hour TTL)
- ⚠️ Need to run populate script hourly OR fix database

### Expected Enrichment Distribution
After new data arrives (5-10 minutes):
- **FULL**: ~8-10 devices (servers, switches, NAS with CMDB data)
- **PARTIAL**: ~25-30 devices (CCTV cameras, devices with default site)
- **NOT_IN_CMDB**: Devices not in cache

---

## 🔧 Maintenance Commands

### Refresh Dashboard
```bash
# Refresh browser
Ctrl+F5 or Cmd+Shift+R

# Or regenerate dashboard
cd /home/infra/dcim_metrics_project
python3 scripts/create_monitoring_dashboard.py
```

### Maintain Redis Cache (Hourly)
```bash
# Run populate script
cd /home/infra/dcim_metrics_project
python3 scripts/populate_redis_minimal.py

# Or add to crontab
crontab -e
# Add: 0 * * * * cd /home/infra/dcim_metrics_project && python3 scripts/populate_redis_minimal.py
```

### Check Enrichment Status
```bash
# Test enrichment API
curl -s http://localhost:8000/enrich/J901GKXY | jq '.enrichment_status'

# Check Redis keys
redis-cli -h 10.70.0.56 -p 6379 KEYS "asset:sn:*" | wc -l

# Check ES enrichment distribution
curl -k -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' \
  'https://10.70.0.56:9200/dcim-metrics-unified-*/_search' \
  -H 'Content-Type: application/json' \
  -d '{
    "size": 0,
    "query": {"range": {"@timestamp": {"gte": "now-1h"}}},
    "aggs": {"enrichment": {"terms": {"field": "enrichment_status.keyword"}}}
  }' | jq '.aggregations.enrichment.buckets'
```

### Restart Services
```bash
# Enrichment service
sudo lsof -ti:8000 | xargs -r sudo kill -9
cd /home/infra/dcim_metrics_project
screen -dmS enrichment python3 -m uvicorn \
  src.skills.inventory.enrichment.executor:app \
  --host 0.0.0.0 --port 8000

# Verify
curl -s http://localhost:8000/enrich/test 2>/dev/null && echo "✅ Running" || echo "❌ Not running"
```

---

## 🚨 Permanent Fix TODO

### High Priority
1. **Fix PostgreSQL Connection**
   ```bash
   # Test connection
   psql -h 192.168.101.73 -U sot_admin -d dcim_sot -c "SELECT 1;"
   
   # Check firewall
   sudo iptables -L -n | grep 5432
   
   # Check PostgreSQL server
   ssh admin@192.168.101.73
   sudo systemctl status postgresql
   sudo netstat -tlnp | grep 5432
   ```

2. **Alternative: Local CMDB**
   - Export CMDB data from PostgreSQL
   - Import to local SQLite or PostgreSQL
   - Update redis_sync config to use local DB

### Medium Priority
3. **Automate Redis Population**
   - Add cron job for hourly refresh
   - Or increase TTL to 24 hours
   - Or fix database connection

4. **Monitor Enrichment Quality**
   - Create alert for enrichment_status distribution
   - Track FULL vs PARTIAL ratio
   - Alert if FULL drops below threshold

---

## 📋 Files Modified/Created

### Created
- `scripts/fix_dashboard_index_pattern.py` - Fix index pattern fields
- `scripts/populate_redis_minimal.py` - Populate Redis without database
- `docs/DASHBOARD_FIX_SUMMARY.md` - This file

### Modified
- `src/skills/inventory/enrichment/executor.py` - Fixed Redis key lookup (yesterday)

### Scripts to Run
```bash
# Fix dashboard (one-time)
python3 scripts/fix_dashboard_index_pattern.py

# Populate Redis (hourly or until DB fixed)
python3 scripts/populate_redis_minimal.py
```

---

## ✅ Verification Checklist

After fixes applied:

- [x] Index pattern has 583 fields
- [x] Redis has 43 device entries
- [x] Enrichment service returns FULL status
- [ ] Dashboard loads without errors
- [ ] Server Details table shows data
- [ ] Enrichment Status pie chart shows FULL (wait 5-10 min)
- [ ] All metric panels display values
- [ ] Time series charts show trends

---

**Fixed**: 2026-05-13 08:30  
**Status**: ✅ Temporary fixes applied  
**Next**: Fix PostgreSQL connection or automate Redis population

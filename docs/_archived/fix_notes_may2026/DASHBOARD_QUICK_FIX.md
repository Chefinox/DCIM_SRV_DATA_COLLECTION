# Dashboard Quick Fix Guide

## 🚀 Quick Commands

### Check Dashboard Status
```bash
# Open dashboard
http://10.70.0.56:5601/app/dashboards#/view/dcim-monitoring

# Check if index pattern has fields
curl -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' \
  'http://10.70.0.56:5601/api/saved_objects/index-pattern/dcim-metrics-*' \
  | jq '.attributes.fields | fromjson | length'
# Should return: 583
```

### Fix "No results found"
```bash
cd /home/infra/dcim_metrics_project
python3 scripts/fix_dashboard_index_pattern.py
```

### Fix Enrichment PARTIAL
```bash
cd /home/infra/dcim_metrics_project
python3 scripts/populate_redis_minimal.py
```

### Check Enrichment Status
```bash
# Test API
curl -s http://localhost:8000/enrich/J901GKXY | jq '.enrichment_status'

# Check Redis
redis-cli -h 10.70.0.56 -p 6379 KEYS "asset:sn:*" | wc -l

# Check in Elasticsearch (last hour)
curl -k -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' \
  'https://10.70.0.56:9200/dcim-metrics-unified-*/_search' \
  -H 'Content-Type: application/json' \
  -d '{"size":0,"query":{"range":{"@timestamp":{"gte":"now-1h"}}},"aggs":{"enrichment":{"terms":{"field":"enrichment_status.keyword"}}}}' \
  | jq '.aggregations.enrichment.buckets'
```

### Restart Enrichment Service
```bash
# Kill old process
sudo lsof -ti:8000 | xargs -r sudo kill -9

# Start new
cd /home/infra/dcim_metrics_project
screen -dmS enrichment python3 -m uvicorn \
  src.skills.inventory.enrichment.executor:app \
  --host 0.0.0.0 --port 8000

# Verify
sleep 2 && curl -s http://localhost:8000/enrich/test 2>/dev/null && echo "✅ Running"
```

---

## 📊 Expected Results

### Dashboard
- **URL**: http://10.70.0.56:5601/app/dashboards#/view/dcim-monitoring
- **Panels**: 34 total
- **Refresh**: 30 seconds
- **Time range**: Last 1 hour

### Enrichment Status (after 10 minutes)
- **FULL**: 10-15% (devices in CMDB)
- **PARTIAL**: 80-85% (devices with default site)
- **NOT_IN_CMDB**: 5-10% (unknown devices)

### Server Details Table
Should show:
- Hostname
- Model
- Temperature (°C)
- Power (W)

---

## 🔧 Troubleshooting

### Dashboard shows "No results found"
```bash
# Fix index pattern
python3 scripts/fix_dashboard_index_pattern.py

# Refresh browser
Ctrl+F5
```

### Enrichment 100% PARTIAL
```bash
# Populate Redis
python3 scripts/populate_redis_minimal.py

# Wait 5-10 minutes for new data
# Or check immediately
curl -s http://localhost:8000/enrich/J901GKXY | jq '.enrichment_status'
```

### Enrichment service not responding
```bash
# Check if running
ps aux | grep "enrichment/executor"

# Check port
sudo lsof -i:8000

# Restart
sudo lsof -ti:8000 | xargs -r sudo kill -9
cd /home/infra/dcim_metrics_project
screen -dmS enrichment python3 -m uvicorn \
  src.skills.inventory.enrichment.executor:app \
  --host 0.0.0.0 --port 8000
```

### Redis cache empty
```bash
# Check keys
redis-cli -h 10.70.0.56 -p 6379 KEYS "asset:sn:*" | wc -l

# If 0 or low, populate
python3 scripts/populate_redis_minimal.py

# Verify
redis-cli -h 10.70.0.56 -p 6379 GET "asset:sn:j901gkxy"
```

---

## ⚠️ Known Issues

### PostgreSQL CMDB Not Accessible
**Error**: `connection to server at "192.168.101.73", port 5432 failed: Connection timed out`

**Workaround**: 
- Run `populate_redis_minimal.py` hourly (automated via cron)
- Data has 1-hour TTL

**Permanent Fix**:
- Restore database connectivity
- Check firewall rules
- Or migrate to local database

### Cron Job
```bash
# Check cron
crontab -l | grep maintain_redis

# Should show:
# 0 * * * * /home/infra/dcim_metrics_project/scripts/maintain_redis_cache.sh

# Check logs
tail -f /home/infra/dcim_metrics_project/logs/redis_populate.log
```

---

## 📞 Support

### Check All Services
```bash
# Enrichment
curl -s http://localhost:8000/enrich/test 2>/dev/null && echo "✅ Enrichment OK"

# Redis
redis-cli -h 10.70.0.56 -p 6379 PING && echo "✅ Redis OK"

# Elasticsearch
curl -k -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' \
  'https://10.70.0.56:9200/_cluster/health' | jq '.status' && echo "✅ ES OK"

# Kibana
curl -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' \
  'http://10.70.0.56:5601/api/status' | jq '.status.overall.level' && echo "✅ Kibana OK"
```

### Full System Check
```bash
cd /home/infra/dcim_metrics_project
./scripts/check_system_health.sh
```

---

**Last Updated**: 2026-05-13  
**Status**: ✅ Fixes applied, monitoring required

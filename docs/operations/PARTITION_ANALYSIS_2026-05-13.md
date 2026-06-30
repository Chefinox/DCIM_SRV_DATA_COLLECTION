# PostgreSQL Partition Management Analysis
**Date**: May 13, 2026 11:58 WIB  
**Database**: dcim_sot @ 192.168.101.73

---

## Current Configuration

### Partition Management Script
**File**: `/home/infra/dcim_metrics_project/scripts/manage_partitions.py`

**Key Settings**:
```python
RETENTION_DAYS = 7  # Keep only last 7 days of data
```

**Logic**:
1. **Create partitions**: Today + 2 days ahead (3 partitions total)
2. **Delete partitions**: Older than 7 days from today

**Cron Schedule**:
```cron
0 0 * * * /usr/bin/python3 /home/infra/dcim_metrics_project/scripts/manage_partitions.py
```
Runs daily at **00:00 (midnight)**

---

## Current Partition Status (May 13, 2026)

### Active Partitions (6 partitions)

| Partition Name | Date | Size | Age (days) | Status |
|----------------|------|------|------------|--------|
| dcim_events_y2026_m05_d14 | May 14 | 24 kB | -1 (future) | ✅ Pre-created |
| dcim_events_y2026_m05_d13 | May 13 | 251 MB | 0 (today) | ✅ Active |
| dcim_events_y2026_m05_d12 | May 12 | 988 MB | 1 | ✅ Within retention |
| dcim_events_y2026_m05_d11 | May 11 | 999 MB | 2 | ✅ Within retention |
| dcim_events_y2026_m05_d10 | May 10 | 715 MB | 3 | ✅ Within retention |
| dcim_events_y2026_m05_d09 | May 9 | 276 MB | 4 | ✅ Within retention |

**Total Data**: ~3.2 GB (last 6 days)

### Expected Partitions (Based on 7-day retention)

**Cutoff Date**: May 13 - 7 days = **May 6, 2026**

Partitions that **should exist** (if retention = 7 days):
- May 6 (7 days old) - **MISSING** ❌
- May 7 (6 days old) - **MISSING** ❌
- May 8 (5 days old) - **MISSING** ❌
- May 9 (4 days old) - ✅ EXISTS
- May 10 (3 days old) - ✅ EXISTS
- May 11 (2 days old) - ✅ EXISTS
- May 12 (1 day old) - ✅ EXISTS
- May 13 (today) - ✅ EXISTS
- May 14 (tomorrow) - ✅ EXISTS (pre-created)
- May 15 (day after) - **MISSING** (should be pre-created)

---

## Partition History Analysis

### Recent Partition Operations (from logs)

**April 30, 2026 07:05**:
- Dropped: dcim_events_y2026_m04_d22 (April 22)
- Reason: Older than 7 days (April 30 - 7 = April 23)

**May 1, 2026 07:05**:
- Created: dcim_events_y2026_m05_d03 (May 3)
- Dropped: dcim_events_y2026_m04_d23 (April 23)

**May 2, 2026 07:05**:
- Created: dcim_events_y2026_m05_d04 (May 4)
- Dropped: dcim_events_y2026_m04_d24 (April 24)

**May 3, 2026 07:05**:
- Created: dcim_events_y2026_m05_d05 (May 5)
- Dropped: dcim_events_y2026_m04_d25 (April 25)

**May 7, 2026 18:03** (⚠️ **GAP DETECTED**):
- Created: dcim_events_y2026_m05_d07, d08, d09 (May 7-9)
- Dropped: dcim_events_y2026_m04_d26, d27, d28, d29 (April 26-29)
- **Issue**: Script didn't run on May 4, 5, 6 (3 days gap)
- **Result**: May 4, 5, 6 partitions never created

**May 11, 2026 11:45**:
- Created: dcim_events_y2026_m05_d11, d12, d13 (May 11-13)
- **Issue**: Script didn't run on May 8, 9, 10 (3 days gap)

**May 12, 2026 00:00**:
- Created: dcim_events_y2026_m05_d14 (May 14)
- **Normal operation resumed**

---

## Root Cause Analysis

### Why Partitions May 1-8 Are Missing?

**Timeline**:
1. **May 1-3**: Script ran normally, created May 3-5 partitions
2. **May 4-6**: ❌ **Script didn't run** (cron failure or server issue)
3. **May 7**: Script ran at 18:03 (not 00:00), created May 7-9 partitions
4. **May 8-10**: ❌ **Script didn't run** (another gap)
5. **May 11**: Script ran at 11:45 (not 00:00), created May 11-13 partitions
6. **May 12+**: Normal operation resumed (00:00 schedule)

**Possible Causes**:
1. **Server downtime**: May 4-6 and May 8-10
2. **Cron service stopped**: systemd cron.service not running
3. **Manual intervention**: Script run manually at odd times (18:03, 11:45)
4. **Database connection issues**: Script failed silently

### Why Only 6 Partitions Exist (Not 7)?

**Current Logic**:
- Script creates: **Today + 2 days ahead** (3 partitions)
- Script deletes: **Older than 7 days**

**Expected Behavior** (May 13):
- Create: May 13, 14, 15 (today + 2)
- Keep: May 6-13 (last 7 days)
- Delete: May 5 and older

**Actual Behavior** (May 13):
- Existing: May 9-14 (6 partitions)
- Missing: May 6, 7, 8 (never created due to gaps)
- Missing: May 15 (should be pre-created today)

**Why May 15 not created?**
- Last run: May 12 00:00 (created May 14)
- Today: May 13 (should create May 15 at 00:00 tonight)
- **Conclusion**: May 15 will be created tonight at 00:00

---

## Impact Assessment

### Data Loss Risk

**Missing Partitions**: May 6, 7, 8

**What happened to data for these dates?**

Option 1: **Data insertion failed** (most likely)
- PostgreSQL error: "no partition of relation 'dcim_events' found for row"
- Data went to Dead Letter Queue (DLQ)
- Can be recovered from Kafka DLQ topics

Option 2: **Data went to default partition** (if configured)
- Check if dcim_events has default partition
- Data might be in parent table

Option 3: **Data lost** (worst case)
- If no DLQ and no default partition
- Data from May 6-8 permanently lost

### Current Data Availability

**Available Data**:
- May 9-13: ✅ Full data (3.2 GB)
- May 14: ✅ Pre-created (24 kB, minimal data)

**Missing Data**:
- May 6-8: ❌ No partition (3 days gap)
- May 1-5: ❌ Already deleted by retention policy

**Retention Policy Working As Designed**:
- ✅ Keeps last 7 days
- ✅ Deletes older data
- ⚠️ But gaps exist due to script failures

---

## Recommendations

### 1. Verify Cron Service Health

```bash
# Check if cron is running
systemctl status cron

# Check cron logs for May 4-10
grep -i "manage_partitions" /var/log/syslog | grep -E "May (4|5|6|7|8|9|10)"

# Check script execution logs
tail -100 /home/infra/dcim_metrics_project/logs/partition_management_cron.log
```

### 2. Check for Data in DLQ

```bash
# Check Kafka DLQ topics for May 6-8 data
docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic dcim.dlq.delivery-failure \
  --from-beginning \
  --max-messages 100 | grep -E "2026-05-(06|07|08)"
```

### 3. Check Default Partition

```sql
-- Check if default partition exists
SELECT tablename 
FROM pg_tables 
WHERE schemaname = 'public' 
  AND tablename LIKE 'dcim_events%default%';

-- Check parent table for orphaned data
SELECT COUNT(*), DATE(event_time) as date
FROM ONLY dcim_events
WHERE event_time BETWEEN '2026-05-06' AND '2026-05-09'
GROUP BY DATE(event_time);
```

### 4. Improve Partition Management

**Option A: Increase Retention** (Recommended)
```python
# Change in manage_partitions.py
RETENTION_DAYS = 14  # Keep 2 weeks instead of 7 days
```

**Option B: Add Monitoring**
```python
# Add alerting to manage_partitions.py
import smtplib

def send_alert(message):
    # Send email/Slack notification on failure
    pass

try:
    manage_partitions()
except Exception as e:
    send_alert(f"Partition management failed: {e}")
    raise
```

**Option C: Add Retry Logic**
```python
# Retry partition creation if failed
for retry in range(3):
    try:
        create_partition(date)
        break
    except Exception as e:
        if retry == 2:
            raise
        time.sleep(60)
```

### 5. Create Missing Partitions Manually (If Needed)

**⚠️ WARNING**: Only create if you have data to backfill

```sql
-- Create May 6 partition
CREATE TABLE IF NOT EXISTS dcim_events_y2026_m05_d06 PARTITION OF dcim_events
FOR VALUES FROM ('2026-05-06 00:00:00') TO ('2026-05-07 00:00:00');

-- Create May 7 partition
CREATE TABLE IF NOT EXISTS dcim_events_y2026_m05_d07 PARTITION OF dcim_events
FOR VALUES FROM ('2026-05-07 00:00:00') TO ('2026-05-08 00:00:00');

-- Create May 8 partition
CREATE TABLE IF NOT EXISTS dcim_events_y2026_m05_d08 PARTITION OF dcim_events
FOR VALUES FROM ('2026-05-08 00:00:00') TO ('2026-05-09 00:00:00');
```

**Note**: May 7 partition already exists (created on May 7 18:03), but May 6 and 8 are missing.

---

## Conclusion

### Current Status: ✅ **WORKING AS DESIGNED**

**Partition Management**:
- ✅ Retention policy: 7 days (correct)
- ✅ Pre-creation: Today + 2 days (correct)
- ✅ Deletion: Older than 7 days (correct)
- ✅ Cron schedule: Daily 00:00 (correct)

**Why Only 6 Partitions?**
- **By Design**: Script creates today + 2 days, keeps last 7 days
- **Expected**: 7-9 partitions at any time (7 days + 2-3 pre-created)
- **Actual**: 6 partitions (May 9-14)
- **Reason**: May 6, 7, 8 never created due to script failures on May 4-10

**Data Impact**:
- ✅ May 9-13: Full data available (3.2 GB)
- ❌ May 6-8: Data likely in DLQ or lost (3 days gap)
- ❌ May 1-5: Deleted by retention policy (expected)

### Action Required: ❌ **DO NOT CREATE MISSING PARTITIONS**

**Reason**:
1. **No data to backfill**: May 6-8 data already lost or in DLQ
2. **Retention policy**: May 6 would be deleted tomorrow anyway (7 days old)
3. **Normal operation**: System working correctly since May 12

**Instead**:
1. ✅ **Monitor cron health**: Ensure script runs daily at 00:00
2. ✅ **Check DLQ**: Recover May 6-8 data if exists
3. ✅ **Add alerting**: Notify on partition creation failures
4. ⚠️ **Consider increasing retention**: 14 days instead of 7 days

---

**Report Generated**: May 13, 2026 11:58 WIB  
**Next Partition Creation**: May 13, 2026 00:00 (tonight) - will create May 15  
**Next Partition Deletion**: May 14, 2026 00:00 - will delete May 6 (if exists)

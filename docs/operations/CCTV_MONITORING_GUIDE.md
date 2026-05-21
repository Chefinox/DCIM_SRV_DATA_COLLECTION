# CCTV Monitoring via NVR - Quick Reference

> **Last Updated**: 2026-05-21  
> **NVR**: Hikvision DS-7732 (192.168.1.254)  
> **Total CCTV**: 31 units  
> **Ralph CMDB**: 20 CCTV terdaftar di Back Office Assets (re-registered 2026-05-19)

---

## ✅ Status Saat Ini

**Semua 31 CCTV Online** (verified via NVR ISAPI)

### CMDB Integration (v3.5.1+)
- **20 CCTV** terdaftar di Ralph Back Office Assets (id=70-89)
- **Remarks** berisi: `IP: 192.168.1.x | Model: DS-2CDxxx | Location: xxx`
- **Auto-sync**: `ralph_cmdb_sync.py` (cron 02:00 WIB) update hostname, IP, firmware
- **Registration script**: `scripts/register_cctv_to_ralph.py`
- **Auto-register exception (v3.5.5)**: CCTV tidak ikut auto-register DC Asset; tetap Back Office Asset via registration script.

### Monitoring Pipeline
- **Poller**: `dcim-cctv-poller.service` (Hikvision ISAPI, interval 120s)
- **Kafka Topic**: `dcim.raw.device.isapi`
- **Elasticsearch**: `dcim-metrics-unified-*` (device_type=cctv/nvr)
- **Dashboard**: Kibana `dcim-monitoring` → CCTV/NVR section
- **Threshold Alert**: NVR Memory >90% (`dcim-threshold-alerter.service`)
- **Stale Detection**: NVR masuk stale-device check 30 menit; CCTV detail tetap dicek via NVR/poller.

---

## 📋 Daftar CCTV Berdasarkan Lokasi

| Ch | IP | Lokasi | Status |
|----|----------------|--------------------------------|--------|
| 1  | 192.168.1.19   | Gate Out 1                     | 🟢 Online |
| 2  | 192.168.1.16   | Gate Out 2                     | 🟢 Online |
| 3  | 192.168.1.6    | Gate In                        | 🟢 Online |
| 4  | 192.168.1.22   | Showroom 2                     | 🟢 Online |
| 5  | 192.168.1.20   | Showroom 1                     | 🟢 Online |
| 6  | 192.168.1.7    | R. Resepsionis                 | 🟢 Online |
| 7  | 192.168.1.8    | R. Meeting Lt.1                | 🟢 Online |
| 8  | 192.168.1.13   | R. Infra                       | 🟢 Online |
| 9  | 192.168.1.24   | Break Room                     | 🟢 Online |
| 10 | 192.168.1.11   | Musholla                       | 🟢 Online |
| 11 | 192.168.1.3    | R. Content 2 View1             | 🟢 Online |
| 12 | 192.168.1.2    | R. Content 2 View2             | 🟢 Online |
| 13 | 192.168.1.9    | R. Lead Content                | 🟢 Online |
| 14 | 192.168.1.21   | R. Project Lt.1                | 🟢 Online |
| 15 | 192.168.1.12   | View Gudang & Toilet Lt.1      | 🟢 Online |
| 16 | 192.168.1.18   | Pantry                         | 🟢 Online |
| 17 | 192.168.1.5    | R. Server                      | 🟢 Online |
| 18 | 192.168.1.14   | View FAT & CEO Lt.2            | 🟢 Online |
| 19 | 192.168.1.23   | R. Procurement                 | 🟢 Online |
| 20 | 192.168.1.10   | R. Content 4 Lt.2              | 🟢 Online |
| 21 | 192.168.1.17   | R. SD 1 Lt.2                   | 🟢 Online |
| 22 | 192.168.1.15   | View Koridor Lt.2              | 🟢 Online |
| 23 | 192.168.1.4    | Koridor Mess Lt.2              | 🟢 Online |
| 24 | 192.168.1.25   | Gudang Lt.2                    | 🟢 Online |
| 25 | 192.168.1.26   | R. Project Lt.2                | 🟢 Online |
| 26 | 192.168.1.27   | R.BD                           | 🟢 Online |
| 27 | 192.168.1.28   | R.SD 2 Lt.2                    | 🟢 Online |
| 28 | 192.168.1.29   | R.Content 1 Lt.2               | 🟢 Online |
| 29 | 192.168.1.30   | R. HRD                         | 🟢 Online |
| 30 | 192.168.1.31   | View Tangga                    | 🟢 Online |
| 31 | 192.168.1.33   | R. Security                    | 🟢 Online |

---

## 🔍 Cara Cek Status CCTV dari NVR

### 1. Via Script Python
```bash
cd /home/infra/dcim_metrics_project
python3 scripts/check_cctv_status.py
```

### 2. Via Curl (Manual)

**List semua channel:**
```bash
curl -s --digest -u "admin:qRvbi883=Zk[Q)@5" \
  "http://192.168.1.254/ISAPI/ContentMgmt/InputProxy/channels" \
  | grep -E "(id>|name>|ipAddress>)"
```

**Cek status online/offline:**
```bash
curl -s --digest -u "admin:qRvbi883=Zk[Q)@5" \
  "http://192.168.1.254/ISAPI/ContentMgmt/InputProxy/channels/status" \
  | grep -E "(<id>|<online>)" | paste - -
```

**Count online cameras:**
```bash
curl -s --digest -u "admin:qRvbi883=Zk[Q)@5" \
  "http://192.168.1.254/ISAPI/ContentMgmt/InputProxy/channels/status" \
  | grep -c "<online>true</online>"
```

### 3. Via PostgreSQL (Data Collected)
```sql
-- Cek CCTV yang terdeteksi dalam 24 jam terakhir
SELECT COUNT(DISTINCT hostname) as total_cctv, 
       COUNT(DISTINCT serial_number) as unique_sn
FROM dcim_events 
WHERE device_type = 'cctv' 
  AND event_time > NOW() - INTERVAL '1 day';

-- List CCTV dengan serial number
SELECT DISTINCT hostname, serial_number 
FROM dcim_events 
WHERE device_type = 'cctv' 
  AND event_time > NOW() - INTERVAL '1 day' 
ORDER BY hostname;
```

---

## 📊 Monitoring Pipeline

```
CCTV (31 units)
    ↓
NVR (192.168.1.254) ← Centralized management
    ↓
Telegraf (hikvision_poller.py) ← Polling every 120s
    ↓
Kafka (dcim.raw.device.isapi)
    ↓
Normalizer → Enrichment → PostgreSQL
    ↓
Ralph CMDB (Daily 02:00 WIB)
```

> [!NOTE]
> `ralph_cmdb_sync.py` v3.5.5 auto-register hanya untuk DC assets (`server`, `ups`, `nas`, `network_switch`, `nvr`). CCTV tetap Back Office Asset dan dikelola via `scripts/register_cctv_to_ralph.py`.

---

## ⚠️ Troubleshooting

### CCTV tidak terdeteksi di PostgreSQL
1. **Cek status di NVR** (gunakan curl command di atas)
2. **Cek Telegraf logs**:
   ```bash
   sudo journalctl -u telegraf -f | grep -i hikvision
   ```
3. **Test manual polling**:
   ```bash
   cd /home/infra/dcim_metrics_project
   python3 scripts/hikvision_poller.py | head -50
   ```

### CCTV offline di NVR
1. Cek koneksi network ke IP camera
2. Ping camera: `ping 192.168.1.X`
3. Cek credential camera (default: admin / F!tech0918)
4. Restart camera via web interface atau power cycle

### Data tidak masuk ke Kafka
1. Cek Kafka topics:
   ```bash
   docker exec kafka-broker /opt/kafka/bin/kafka-topics.sh \
     --bootstrap-server localhost:9092 --list | grep isapi
   ```
2. Peek Kafka messages:
   ```bash
   docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh \
     --bootstrap-server localhost:9092 \
     --topic dcim.raw.device.isapi \
     --from-beginning --max-messages 5
   ```

---

## 📝 Notes

- **IP Range**: 192.168.1.2-33 (skip .32 - tidak digunakan)
- **Polling Interval**: 120 seconds (2 minutes)
- **Protocol**: ISAPI HTTP (Port 80)
- **Authentication**: Basic Auth (admin / qRvbi883=Zk[Q)@5)
- **NVR Model**: Hikvision DS-7732
- **Camera Models**: DS-2CD1021-I, DS-2CD1043G0E-I, DS-2CD1121-I, DS-2CD1143G0E-I, DS-2CD3121G0-I

---

**Last Updated**: 2026-05-21 00:30 WIB

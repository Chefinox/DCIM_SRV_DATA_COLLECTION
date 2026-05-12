# CCTV Status Summary

**Verified**: 2026-05-12 11:53 WIB  
**Method**: NVR ISAPI Query

---

## ✅ Status: ALL ONLINE

```
Total CCTV: 31 units
Online:     31 units (100%)
Offline:    0 units
```

---

## 📍 Coverage Map

### Lantai 1 (15 cameras)
- ✅ Gate Out 1 (192.168.1.19)
- ✅ Gate Out 2 (192.168.1.16)
- ✅ Gate In (192.168.1.6)
- ✅ Showroom 1 (192.168.1.20)
- ✅ Showroom 2 (192.168.1.22)
- ✅ R. Resepsionis (192.168.1.7)
- ✅ R. Meeting Lt.1 (192.168.1.8)
- ✅ R. Infra (192.168.1.13)
- ✅ Break Room (192.168.1.24)
- ✅ Musholla (192.168.1.11)
- ✅ R. Content 2 View1 (192.168.1.3)
- ✅ R. Content 2 View2 (192.168.1.2)
- ✅ R. Lead Content (192.168.1.9)
- ✅ R. Project Lt.1 (192.168.1.21)
- ✅ View Gudang & Toilet Lt.1 (192.168.1.12)

### Lantai 2 (15 cameras)
- ✅ Pantry (192.168.1.18)
- ✅ R. Server (192.168.1.5)
- ✅ View FAT & CEO Lt.2 (192.168.1.14)
- ✅ R. Procurement (192.168.1.23)
- ✅ R. Content 4 Lt.2 (192.168.1.10)
- ✅ R. SD 1 Lt.2 (192.168.1.17)
- ✅ View Koridor Lt.2 (192.168.1.15)
- ✅ Koridor Mess Lt.2 (192.168.1.4)
- ✅ Gudang Lt.2 (192.168.1.25)
- ✅ R. Project Lt.2 (192.168.1.26)
- ✅ R.BD (192.168.1.27)
- ✅ R.SD 2 Lt.2 (192.168.1.28)
- ✅ R.Content 1 Lt.2 (192.168.1.29)
- ✅ R. HRD (192.168.1.30)
- ✅ View Tangga (192.168.1.31)

### Security Room (1 camera)
- ✅ R. Security (192.168.1.33)

---

## 🔧 Quick Commands

**Check status via NVR:**
```bash
curl -s --digest -u "admin:qRvbi883=Zk[Q)@5" \
  "http://192.168.1.254/ISAPI/ContentMgmt/InputProxy/channels/status" \
  | grep -c "<online>true</online>"
```

**Expected output:** `31`

**Check via script:**
```bash
cd /home/infra/dcim_metrics_project
python3 scripts/check_cctv_status.py
```

**Check via PostgreSQL:**
```sql
SELECT COUNT(DISTINCT serial_number) 
FROM dcim_events 
WHERE device_type = 'cctv' 
  AND event_time > NOW() - INTERVAL '5 minutes';
```

---

## 📊 Monitoring Integration

- **NVR**: Hikvision DS-7732 (192.168.1.254)
- **Telegraf Polling**: Every 120 seconds
- **Kafka Topic**: `dcim.raw.device.isapi`
- **PostgreSQL**: `dcim_events` table
- **Ralph CMDB**: Daily sync at 02:00 WIB

---

**For detailed guide, see:** `docs/operations/CCTV_MONITORING_GUIDE.md`

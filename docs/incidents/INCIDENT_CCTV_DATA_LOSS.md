# Incident Report: CCTV Data Loss dari Migrasi Ralph

**Incident Date:** ~2026 (sebelum May 12)  
**Discovery Date:** 2026-05-12  
**Severity:** Medium  
**Status:** Recovery in Progress

---

## 📋 Executive Summary

21 dari 31 CCTV asset records hilang dari Ralph CMDB database setelah incident migrasi gagal dan recovery data yang tidak sempurna. CCTV-CCTV ini sebelumnya sudah terdaftar di back office tapi data hilang dari database.

---

## 🔍 Root Cause Analysis

### Timeline
1. **Before Incident:** 31 CCTV terdaftar di Ralph CMDB (back office)
2. **Incident:** Migrasi Ralph database gagal
3. **Recovery Attempt:** Data recovery dilakukan tapi tidak sempurna
4. **Result:** Hanya ~10 CCTV yang berhasil ter-recover
5. **Discovery:** 2026-05-12 - Terdeteksi saat analisis ralph_cmdb_sync.log

### Impact Assessment
- **Data Loss:** 21 CCTV asset records (67% dari total CCTV)
- **Affected Models:**
  - DS-2CD1121-I: 14 unit (mayoritas)
  - DS-2CD1043G0E-I: 2 unit
  - DS-2CD1143G0E-I: 2 unit
  - DS-2CD1021-I: 1 unit
  - DS-2CD3121G0-I: 1 unit

### Technical Impact
- ❌ Metadata sync gagal (location, owner, department)
- ❌ Warning logs di ralph_cmdb_sync: "tidak ditemukan di Ralph, skip"
- ✅ Metrics collection tetap berjalan (tidak terpengaruh)
- ✅ CCTV tetap operational dan online

---

## 📊 Affected Assets

### Complete List of Missing CCTVs

| No | Serial Number | Model | Status |
|----|---------------|-------|--------|
| 1  | DS-2CD1043G0E-I20200427AAWRE30076984 | DS-2CD1043G0E-I | Missing |
| 2  | DS-2CD1121-I20200308AAWRE17568965 | DS-2CD1121-I | Missing |
| 3  | DS-2CD1121-I20200308AAWRE17568450 | DS-2CD1121-I | Missing |
| 4  | DS-2CD1121-I20200308AAWRE17568469 | DS-2CD1121-I | Missing |
| 5  | DS-2CD1043G0E-I20200427AAWRE30076719 | DS-2CD1043G0E-I | Missing |
| 6  | DS-2CD1121-I20200308AAWRE17568933 | DS-2CD1121-I | Missing |
| 7  | DS-2CD1143G0E-I20210227AAWRF58406256 | DS-2CD1143G0E-I | Missing |
| 8  | DS-2CD1121-I20200308AAWRE17568170 | DS-2CD1121-I | Missing |
| 9  | DS-2CD1143G0E-I20210227AAWRF58406296 | DS-2CD1143G0E-I | Missing |
| 10 | DS-2CD1021-I20201119AAWRE99707505 | DS-2CD1021-I | Missing |
| 11 | DS-2CD1121-I20200308AAWRE17568951 | DS-2CD1121-I | Missing |
| 12 | DS-2CD1121-I20200308AAWRE17568954 | DS-2CD1121-I | Missing |
| 13 | DS-2CD1121-I20200308AAWRE17568952 | DS-2CD1121-I | Missing |
| 14 | DS-2CD1121-I20200308AAWRE17568968 | DS-2CD1121-I | Missing |
| 15 | DS-2CD1121-I20200308AAWRE17568966 | DS-2CD1121-I | Missing |
| 16 | DS-2CD1121-I20200308AAWRE17568967 | DS-2CD1121-I | Missing |
| 17 | DS-2CD1121-I20200308AAWRE17568953 | DS-2CD1121-I | Missing |
| 18 | DS-2CD1121-I20200308AAWRE17568949 | DS-2CD1121-I | Missing |
| 19 | DS-2CD1121-I20200308AAWRE17568950 | DS-2CD1121-I | Missing |
| 20 | DS-2CD1121-I20200308AAWRE17568948 | DS-2CD1121-I | Missing |
| 21 | DS-2CD3121G0-I20200427AAWRE30076984 | DS-2CD3121G0-I | Missing |

**Note:** Semua CCTV ini berada di back office (bukan di ruang server)

---

## 🔧 Recovery Actions

### Immediate Actions (2026-05-12)
1. ✅ Identified missing assets via log analysis
2. ✅ Created documentation: `CCTV_MISSING_FROM_RALPH.md`
3. ✅ Created recovery script: `register_missing_cctv_to_ralph.py`
4. ⏳ Pending: Execute re-registration

### Recovery Options

**Option A: Automated Re-registration (Recommended)**
```bash
cd /home/infra/dcim_metrics_project
python3 scripts/register_missing_cctv_to_ralph.py
```

**Option B: Manual Re-registration**
- Login ke Ralph web interface
- Add each CCTV manually dengan data dari tabel di atas
- Map IP addresses (192.168.1.2-33, skip .32)
- Set location sesuai CCTV_STATUS.md

### Post-Recovery Verification
```bash
# 1. Run sync untuk verify
python3 scripts/ralph_cmdb_sync.py

# 2. Check logs - seharusnya tidak ada warning lagi
tail -50 logs/ralph_cmdb_sync.log | grep -i cctv

# 3. Verify count di database
# Should show 31 CCTVs with proper metadata
```

---

## 📝 Lessons Learned

### What Went Wrong
1. **Incomplete Backup:** Backup sebelum migrasi tidak complete atau tidak ter-restore dengan baik
2. **No Verification:** Recovery process tidak di-verify untuk completeness
3. **Delayed Detection:** Data loss baru terdeteksi setelah beberapa waktu

### Preventive Measures
1. **Regular Backups:** Implement automated daily backup Ralph database
2. **Backup Verification:** Test restore process secara berkala
3. **Post-Migration Checklist:** Verify asset counts setelah migrasi/recovery
4. **Monitoring:** Alert jika ada asset yang hilang dari database
5. **Documentation:** Maintain asset inventory di luar Ralph (spreadsheet backup)

### Recommendations
1. **Immediate:** Re-register 21 missing CCTVs
2. **Short-term:** Create backup/restore procedure untuk Ralph
3. **Long-term:** Implement automated asset count monitoring

---

## 📚 Related Documentation

- **Missing Assets List:** `/home/infra/dcim_metrics_project/CCTV_MISSING_FROM_RALPH.md`
- **CCTV Status:** `/home/infra/dcim_metrics_project/CCTV_STATUS.md`
- **Monitoring Guide:** `/home/infra/dcim_metrics_project/docs/operations/CCTV_MONITORING_GUIDE.md`
- **Recovery Script:** `/home/infra/dcim_metrics_project/scripts/register_missing_cctv_to_ralph.py`

---

## 👥 Stakeholders

- **IT Infrastructure Team:** Asset management
- **Security Team:** CCTV operations (tidak terpengaruh)
- **Back Office:** Location owners

---

**Report Prepared By:** AI Agent  
**Date:** 2026-05-12  
**Status:** Open - Recovery in Progress

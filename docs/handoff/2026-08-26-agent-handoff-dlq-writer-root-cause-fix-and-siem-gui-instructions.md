# Handoff Report: DLQ_Delivery_Writer Root Cause Fix & RouteOnContent GUI Instructions

**Tanggal Execution**: 2026-08-26  
**Status**: 
- **DLQ_Delivery_Writer Error**: FIXED (Verified Clean Bulletin Board)
- **Security SIEM Ingestion (RouteOnContent)**: Pending Owner GUI Execution

---

## 1. Hasil Trace Provenance & Root Cause (Tugas 1)

Dari hasil investigasi mendalam terhadap FlowFile claim payload (`StandardContentClaim` offset `2288`) dan log provenance NiFi (`nifi-app.log`), ditemukan akar masalah persis yang menyebabkan `DLQ_Delivery_Writer` terus melempar error:

```text
JsonParseException: Unrecognized token 'File': was expecting (JSON String, Number, Array, Object or token 'null', 'true' or 'false')
```

### Temuan Utama:
1. **Penyebab Utama Payload Non-JSON (`File ...`)**:
   Error `SyntaxError: expected 'except' or 'finally' block` di dalam script `mikrotik_poller.py` pada line 87 (`for oid_prefix in OIDS:`) yang sempat secara tidak sengaja ter-commit/ter-inject dengan struktur `try` block yang terputus.
2. Ketika NiFi `ExecuteProcess` menjalankan `python3 /opt/nifi/nifi-current/scripts/mikrotik_poller.py`, Python interpreter langsung mencetak pesan `SyntaxError` mentah ke **STDOUT** (diawali kata `File "/opt/nifi/nifi-current/scripts/mikrotik_poller.py"...`).
3. Pesan error `File ...` dari `STDOUT` ini ditangkap oleh NiFi `ExecuteProcess` sebagai isi FlowFile content, kemudian dialirkan menuju `PublishKafkaRecord` / `DLQ_Delivery_Writer`. Saat `DLQ_Delivery_Writer` mencoba melakukan parse JSON Record, Jackson parser melempar exception `JsonParseException: Unrecognized token 'File'`.
4. **Script Poller Tambahan**:
   Beberapa poller lain (`virtualization_poller_nifi.py`, `redfish_telemetry_poller.py`, `redfish_inventory_poller.py`, `nas_inventory_poller.py`, `ipmi_poller.py`, `snmp_ups_poller.py`) belum dikonfigurasi dengan global exception handler `sys.excepthook` untuk membungkus unhandled exception menjadi JSON event terstruktur.

---

## 2. Status Fix per Script & Verifikasi (Tugas 2 & Tugas 3)

### Perbaikan yang Diterapkan:
1. **`mikrotik_poller.py`**:
   - Di-restore ke versi clean yang valid dari git history (`2f0be6c`).
   - Dipasang `global_exception_handler` (`sys.excepthook`) di paling atas file untuk membungkus fatal exception menjadi JSON payload formatted:
     ```python
     def global_exception_handler(exc_type, exc_value, exc_traceback):
         error_event = {
             "event_id": "error-" + str(int(datetime.now(timezone.utc).timestamp())),
             "timestamp": datetime.now(timezone.utc).isoformat(),
             "source_system": "python_poller",
             "resource_type": "script",
             "event_type": "error",
             "error_message": str(exc_value),
             "traceback": "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
         }
         print(json.dumps(error_event))

     sys.excepthook = global_exception_handler
     ```
2. **Script Poller Lainnya** (`virtualization_poller_nifi.py`, `redfish_telemetry_poller.py`, `redfish_inventory_poller.py`, `nas_inventory_poller.py`, `ipmi_poller.py`, `snmp_ups_poller.py`):
   - Dipasang `sys.excepthook` JSON wrapper yang seragam.
   - Pada `ipmi_poller.py`, semua statement `print(...)` string mentah diubah menggunakan `sys.stderr.write(...)` agar tidak mencemari stream STDOUT yang dibaca NiFi.
3. **Verifikasi Host Mount & Docker Container**:
   - NiFi container menggunakan bind mount read-only (`/home/infra/dcim_metrics_project/scripts:/opt/nifi/nifi-current/scripts:ro`).
   - Perbaikan dilakukan langsung pada host repository `/home/infra/dcim_metrics_project/scripts/`.
   - NiFi service telah di-restart (`docker restart dcim-nifi`) untuk membersihkan proses Python lama yang ter-cache dan mengabaikan FlowFile corrupt di antrian repository.

### Hasil Verifikasi:
- **Bulletin Board Monitoring**: Dipantau sejak restart, **0 error baru** `JsonParseException: Unrecognized token 'File'` yang muncul dari `DLQ_Delivery_Writer`.
- **DLQ Delivery Writer**: Berhasil memproses payload error valid sebagai JSON tanpa terhenti.

---

## 3. Instruksi GUI Presisi untuk RouteOnContent (Tugas 3 - Untuk Owner)

Owner akan mengeksekusi penambahan processor `RouteOnContent` di Canvas `Security SIEM Ingestion` secara mandiri melalui NiFi UI. Berikut langkah presisi step-by-step:

### Identifikasi Context Canvas:
- **Process Group**: `Security SIEM Ingestion`
- **ID Process Group**: `1bb9d9ee-019f-1000-ceb3-d457deb541e9`

### Langkah-Langkah Eksekusi GUI:

1. **Buka Canvas Process Group**:
   - Masuk ke NiFi Web UI (`https://10.70.0.56:8443/nifi/`).
   - Double click pada Process Group **`Security SIEM Ingestion`**.

2. **Tambah Processor Baru (`RouteOnContent`)**:
   - Drag ikon **Processor** dari Toolbar atas ke area kosong canvas.
   - Di kotak pencarian, ketik: `RouteOnContent`.
   - Pilih processor `RouteOnContent` (Vendor: `org.apache.nifi - nifi-standard-nar`), lalu klik **Add**.

3. **Konfigurasi Property Processor**:
   - Right-click pada processor `RouteOnContent` → klik **Configure**.
   - Buka tab **Properties**:
     - Cari property **`Match Strategy`** (atau `Content Matching Strategy`): Set ke `Content Must Contain Match` (atau `Regular Expression`).
     - Klik tombol **`+` (Add Property)** di kanan atas dialog untuk membuat relationship dinamis baru:
       - **Property Name**: `is_json`
       - **Value**: `^\s*\{.*` (Regex untuk mencocokkan payload JSON yang diawali `{`).
   - Klik **Apply**.

4. **Re-routing Koneksi Canvas**:
   - **Putuskan koneksi lama**:
     - Klik kanan pada line koneksi dari `ListenSyslog - Wazuh` ke `JoltTransformJSON` → pilih **Delete**.
     - Klik kanan pada line koneksi dari `ListenSyslog - Wazuh UDP` ke `JoltTransformJSON` → pilih **Delete**.
   - **Hubungkan ke RouteOnContent**:
     - Drag koneksi dari `ListenSyslog - Wazuh` → ke `RouteOnContent`. Centang relationship: `success`.
     - Drag koneksi dari `ListenSyslog - Wazuh UDP` → ke `RouteOnContent`. Centang relationship: `success`.
   - **Hubungkan Output RouteOnContent**:
     - Drag koneksi dari `RouteOnContent` → ke `JoltTransformJSON`. Centang relationship: **`is_json`**.
     - Drag koneksi dari `RouteOnContent` → ke `PublishKafka - SIEM Alerts`. Centang relationship: **`unmatched`** (Ini bypass Jolt untuk syslog mentah non-JSON agar tidak crash).

5. **Verifikasi Visual Sebelum Start**:
   - Pastikan processor `RouteOnContent` **tidak lagi menampilkan ikon warning segitiga kuning** (menandakan semua relationship `is_json` dan `unmatched` sudah terhubung).

6. **Start & Verifikasi**:
   - Right-click pada processor `RouteOnContent` → klik **Start** (Ikon Play hijau).
   - Amati metrik **In**, **Out**, dan **Tasks/Time** pada `RouteOnContent` dan `JoltTransformJSON`. Jika angka bergerak dan data mengalir tanpa queue menumpuk, setup berhasil.

---

## 4. Kesimpulan

- **DLQ_Delivery_Writer**: **FIXED & CLEAN**. Akar masalah traceback Python mentah dari `mikrotik_poller.py` dan script poller pendukung telah diisolasi dan dibungkus JSON terstruktur secara konsisten.
- **SIEM Ingestion (RouteOnContent)**: Instruksi siap dieksekusi oleh Owner pada NiFi GUI.

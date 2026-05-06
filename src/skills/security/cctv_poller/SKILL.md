# Skill: CCTV Poller

## Purpose
Melakukan polling status dan metadata teknis dari perangkat keamanan (CCTV/NVR) berbasis protokol Hikvision ISAPI.

## Capabilities
- Mengambil informasi teknis perangkat (SN, Model, Firmware).
- Monitoring status kesehatan sistem (CPU, Memory Usage).
- Discovery: Mengambil pemetaan IP-ke-SN dari NVR untuk kamera yang terhubung via proxy.
- Normalisasi output XML mentah menjadi skema DCIM standar.

## Inputs
- `ip`: Alamat IP perangkat target.
- `user`: Username ISAPI.
- `password`: Password ISAPI.
- `device_category`: (Optional) "CCTV" atau "NVR".

## Outputs
- Dictionary berisi metadata teknis dan status online/offline.

## Dependencies
- **Tools**: `HikvisionClient`.
- **Schemas**: `CCTVMetadataTransformer`.

## Execution Flow
1. Inisialisasi koneksi ISAPI ke target.
2. Request endpoint `/System/deviceInfo`.
3. Jika online, ambil status utilitas via `/System/status`.
4. Transformasikan XML mentah menjadi struktur JSON datar.

# Skill: Event Logger

## Purpose
Pencatatan persisten terhadap status aset infrastruktur ke dalam tabel historis `dcim_events`.

## Capabilities
- Melakukan mapping objek DCIM yang sudah diperkaya (enriched) ke skema database PostgreSQL.
- Menghasilkan UUID unik untuk setiap event.
- Mencatat detail hardware (CPU, RAM, Disk, NIC) dalam format JSONB.
- Mengatur timestamp penyisipan data (`inserted_at`).

## Inputs
- `data`: Dictionary objek DCIM lengkap (hasil dari Scanner + Enricher).

## Outputs
- `event_id`: UUID dari record yang berhasil disimpan.

## Dependencies
- **Tools**: `PostgresClient`.

## Execution Flow
1. Menerima objek data lengkap.
2. Memvalidasi ketersediaan field wajib.
3. Melakukan sinkronisasi SQL INSERT ke tabel `dcim_events`.

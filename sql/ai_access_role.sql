-- =============================================================================
-- AI Team Data Access Role  (L14 — Data Interface for AI, v4.2)
-- =============================================================================
-- Prinsip: host srv-rnd-dcim = PENYEDIA DATA, bukan tempat menjalankan AI.
-- Tim AI mengakses dari LUAR dengan privilege minimal (least privilege):
--   * READ-ONLY  : v_train_*, dcim_metrics_archive, dcim_failure_events,
--                  unified_assets, dcim_server_* (komponen)
--   * WRITE-ONLY : dcim_server_anomalies  (wadah hasil skor) + sequence-nya
-- Tidak ada akses superuser, tidak ada CREATE, tidak ada DELETE/UPDATE data lain.
--
-- Idempoten: aman dijalankan berulang.
-- Password TIDAK disimpan di file ini. Set via psql variable :ai_pw, contoh:
--   psql -v ai_pw="'<PASSWORD>'" -f sql/ai_access_role.sql
-- (tanda kutip tunggal di dalam nilai diperlukan, lihat header pemanggilan.)
-- =============================================================================

\set ON_ERROR_STOP on

-- 1) Role login (idempoten). Buat bila belum ada (via \gexec), lalu set
--    password & atribut sebagai statement biasa (substitusi :'ai_pw' di sini
--    bekerja karena berada di LUAR blok dollar-quoted).
SELECT 'CREATE ROLE dcim_ai_reader LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dcim_ai_reader')
\gexec

ALTER ROLE dcim_ai_reader LOGIN PASSWORD :'ai_pw';
ALTER ROLE dcim_ai_reader NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
-- Batas koneksi paralel dari tim AI (lindungi host pipeline dari beban berlebih).
ALTER ROLE dcim_ai_reader CONNECTION LIMIT 10;

-- 2) Hak konek ke database & pakai schema public (tanpa CREATE di schema).
GRANT CONNECT ON DATABASE dcim_sot TO dcim_ai_reader;
GRANT USAGE  ON SCHEMA public      TO dcim_ai_reader;

-- 3) READ-ONLY pada sumber data latih.
GRANT SELECT ON
    v_train_server, v_train_ups, v_train_nas,
    v_train_network, v_train_cctv, v_train_nvr,
    dcim_metrics_archive,
    dcim_failure_events,
    unified_assets,
    dcim_server_disks, dcim_server_ram,
    dcim_server_processors, dcim_server_nics
  TO dcim_ai_reader;

-- 4) WRITE pada WADAH hasil saja (INSERT + UPDATE skor; tanpa DELETE).
--    SELECT diberikan agar tim AI bisa baca-balik hasil yang ia tulis.
GRANT SELECT, INSERT, UPDATE ON dcim_server_anomalies TO dcim_ai_reader;
GRANT USAGE, SELECT ON SEQUENCE dcim_server_anomalies_id_seq TO dcim_ai_reader;

-- 5) Pastikan TIDAK ada akses tulis ke tabel operasional inti.
--    (REVOKE eksplisit sebagai jaring pengaman bila pernah ter-grant.)
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON dcim_events FROM dcim_ai_reader;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON dcim_metrics_archive FROM dcim_ai_reader;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON dcim_failure_events FROM dcim_ai_reader;

-- 6) Verifikasi ringkas (tampil saat dijalankan interaktif).
\echo '--- Grants untuk dcim_ai_reader ---'
SELECT table_name, string_agg(privilege_type, ',' ORDER BY privilege_type) AS privs
FROM information_schema.role_table_grants
WHERE grantee = 'dcim_ai_reader'
GROUP BY table_name
ORDER BY table_name;

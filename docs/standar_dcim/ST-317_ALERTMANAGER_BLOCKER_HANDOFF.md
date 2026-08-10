---
title: "ST-317 Alertmanager Notification Path — Blocker Handoff"
created: 2026-07-28
updated: 2026-07-28
version: 1.0
type: dependency-handoff
block: 7
owner: DCIM Block 7
status: active
confidence: 100%
tags: [prometheus, alertmanager, notification, blocker, st-317]
---

# ST-317 Alertmanager Notification Path — Blocker Handoff

## 1. Ringkasan

ST-317 sudah membuktikan lima Prometheus alert rules Block 7 valid dan mampu melewati lifecycle:

```text
inactive → pending → firing → resolved
```

Prometheus production sehat dan scrape target Block 7 berstatus `up`. Blocker tersisa berada setelah state `firing`: Prometheus belum memiliki tujuan Alertmanager dan belum ada receiver notification yang dapat diverifikasi.

```text
Block 7 API /metrics
        ↓ PASS
Prometheus scrape + rule evaluation
        ↓ PASS
inactive / pending / firing / resolved
        ↓ BLOCKED
Alertmanager routing + grouping + deduplication
        ↓ BLOCKED
Receiver test / n8n / Teams / Telegram / email
```

Dampak: alert terlihat `firing` di Prometheus, tetapi tidak dikirim ke channel tujuan. Notification delivery, resolved notification, grouping, dan duplicate-delivery belum bisa diuji. ST-317 tetap `In Progress`.

## 2. Evidence kondisi aktual

| Pemeriksaan | Hasil | Evidence |
|---|---|---|
| Prometheus production ready | PASS | `implementation/dcim_ai_v2_rag/artifacts/st317/production-baseline-summary.json` |
| Target `dcim_block7_api` | PASS, `up` | `implementation/dcim_ai_v2_rag/artifacts/st317/production-targets.txt` |
| Prometheus config syntax | PASS | `implementation/dcim_ai_v2_rag/artifacts/st317/production-promtool_config.txt` |
| Alert rule syntax | PASS, 5 rules | `implementation/dcim_ai_v2_rag/artifacts/st317/production-promtool_rules.txt` |
| Lifecycle controlled test | PASS, 5/5 | `implementation/dcim_ai_v2_rag/artifacts/st317/controlled-transition-results.json` |
| `alerting.alertmanagers` | MISSING | `implementation/dcim_ai_v2_rag/artifacts/st317/production-config.txt` |
| Notification receiver | NOT AVAILABLE | Tidak ada Alertmanager/receiver pada config production |

Rules yang sudah lulus technical lifecycle:

1. `AnomalyRateHigh` — warning
2. `ModelDriftDetected` — critical
3. `PUEHigh` — warning
4. `RCAHighLatency` — warning
5. `LLMErrorRateHigh` — warning

## 3. Scope dan ownership

Mengikuti batas arsitektur `dcim-wiki` dan standar Block 7:

| Tim | Tanggung jawab |
|---|---|
| Block 7 | Menyediakan metrics, alert expressions, thresholds, labels, annotations, controlled trigger, dan evidence rule lifecycle |
| Block 1 / Core Infra | Menentukan lokasi runtime Alertmanager, networking, deployment, availability, storage/silence, dan konfigurasi Prometheus menuju Alertmanager |
| Block 8 / Workflow Automation | Menentukan receiver/workflow notification, routing eskalasi, channel tujuan, audit delivery, dan remediation guard |

Block 7 tidak akan memasang atau mengubah service monitoring production tanpa persetujuan owner Block 1.

## 4. Kebutuhan dari tim terkait

### 4.1 Keputusan yang dibutuhkan

| ID | Keputusan | Owner utama | Nilai yang perlu diberikan |
|---|---|---|---|
| D-01 | Lokasi Alertmanager | Block 1 | Host/DNS, port, protocol, deployment type |
| D-02 | Receiver test | Block 8 | Webhook non-remediation atau channel test |
| D-03 | Receiver production | Block 8/Operation | n8n, Teams, Telegram, email, PagerDuty, atau kombinasi |
| D-04 | Routing severity | Block 8/Operation | Channel warning dan critical |
| D-05 | Grouping policy | Block 1/8 | `group_by`, `group_wait`, `group_interval` |
| D-06 | Repeat policy | Operation | `repeat_interval` |
| D-07 | Resolved notification | Operation | Disarankan `send_resolved: true` |
| D-08 | Security | Block 1/8 | TLS, auth, secret location, network ACL |
| D-09 | Ownership operasi | Block 1/8 | Owner silence, receiver failure, dan escalation |

### 4.2 Minimum technical deliverables

Tim terkait perlu menyediakan:

1. Alertmanager endpoint yang dapat dijangkau Prometheus Block 7.
2. Receiver test yang hanya mencatat payload dan tidak menjalankan remediation.
3. Alertmanager config dengan grouping dan `send_resolved: true`.
4. Prometheus config berisi `alerting.alertmanagers`.
5. Bukti health Alertmanager dan receiver.
6. PIC untuk mendampingi controlled firing test.
7. Persetujuan window test.

## 5. Contoh konfigurasi target

> Contoh berikut template. Hostname, port, URL, credential, dan routing harus dikonfirmasi owner. Jangan langsung diterapkan ke production.

### 5.1 Prometheus menuju Alertmanager

```yaml
alerting:
  alertmanagers:
    - scheme: http
      static_configs:
        - targets:
            - "alertmanager.example.internal:9093"
```

Jika Prometheus dan Alertmanager berada dalam Docker network yang sama, target dapat memakai service name:

```yaml
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - "alertmanager:9093"
```

### 5.2 Alertmanager menuju receiver test

```yaml
global:
  resolve_timeout: 5m

route:
  receiver: block7-test
  group_by:
    - alertname
    - component
    - severity
  group_wait: 10s
  group_interval: 5m
  repeat_interval: 4h

receivers:
  - name: block7-test
    webhook_configs:
      - url: "https://receiver.example.internal/webhook/dcim-block7-test"
        send_resolved: true
```

### 5.3 Contoh routing critical

```yaml
route:
  receiver: block7-warning
  group_by: [alertname, component]
  group_wait: 10s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - matchers:
        - block="7"
        - severity="critical"
      receiver: block7-critical

receivers:
  - name: block7-warning
    webhook_configs:
      - url: "https://receiver.example.internal/webhook/dcim-block7-warning"
        send_resolved: true

  - name: block7-critical
    webhook_configs:
      - url: "https://receiver.example.internal/webhook/dcim-block7-critical"
        send_resolved: true
```

## 6. Security requirements

1. Jangan menyimpan webhook token, API key, atau password langsung di repository.
2. Simpan secret di Vault, Docker secret, Kubernetes Secret, atau secret manager yang disetujui.
3. Gunakan TLS untuk komunikasi lintas host/network jika tersedia.
4. Batasi network ACL: Prometheus hanya ke Alertmanager; Alertmanager hanya ke receiver yang disetujui.
5. Receiver test tidak boleh melakukan restart, shutdown, ticket closure, atau perubahan production.
6. Log payload harus disanitasi dan tidak memuat credential.
7. Tetapkan retention dan akses log notification.

## 7. Rencana joint validation

Setelah dependency tersedia, Block 7 dan tim terkait menjalankan urutan berikut:

1. Jalankan `promtool check config` dan `promtool check rules`.
2. Verifikasi Prometheus melihat Alertmanager sebagai active target.
3. Verifikasi health Alertmanager.
4. Aktifkan controlled trigger untuk satu rule warning.
5. Buktikan Prometheus state `pending`, lalu `firing`.
6. Buktikan Alertmanager menerima alert.
7. Buktikan receiver menerima satu firing notification.
8. Pertahankan alert dan pastikan tidak ada duplicate delivery di luar policy.
9. Hentikan trigger.
10. Buktikan Prometheus kembali `inactive`.
11. Buktikan receiver menerima resolved notification.
12. Ulangi untuk critical routing.
13. Simpan payload tersanitasi, timestamp, status HTTP, dan screenshot/API output sebagai evidence.

## 8. Acceptance criteria penutupan blocker

| # | Acceptance criterion | Evidence minimum |
|---|---|---|
| 1 | Prometheus terhubung ke Alertmanager | Prometheus runtime config/API dan active Alertmanager target |
| 2 | Alertmanager healthy | Health/readiness output |
| 3 | Warning route benar | Satu warning alert diterima receiver warning/test |
| 4 | Critical route benar | `ModelDriftDetected` diterima receiver critical/test |
| 5 | Label dan annotation utuh | Payload berisi `alertname`, `block`, `component`, `severity`, `summary` |
| 6 | Resolved terkirim | Payload `resolved` diterima setelah trigger dihentikan |
| 7 | Grouping sesuai policy | Alert dikelompokkan sesuai `group_by` |
| 8 | Tidak ada duplicate berlebih | Delivery count sesuai `group_interval`/`repeat_interval` |
| 9 | Receiver failure terpantau | Error delivery terlihat di metric/log Alertmanager |
| 10 | Tidak ada remediation production | Receiver test hanya mencatat payload |

ST-317 dapat diubah menjadi `Done` setelah seluruh acceptance criterion notification lulus dan evidence ditambahkan ke `ST-317_EXECUTION_REPORT.md`.

## 9. Informasi yang diminta untuk dibalas

Mohon tim terkait mengisi:

```text
Alertmanager owner/PIC:
Alertmanager host atau DNS:
Port dan protocol:
Deployment type:
Receiver test URL/type:
Receiver production channel:
Warning route:
Critical route:
Grouping policy:
Repeat interval:
Resolved notification: yes/no
Secret management method:
Network/TLS requirement:
Proposed test window:
PIC saat validation:
```

## 10. Template pesan singkat

Halo Tim Block 1 dan Block 8,

ST-317 Prometheus Alert Rules Firing Test Block 7 sudah lulus untuk 5/5 rules pada lifecycle `inactive → pending → firing → resolved`. Prometheus production juga sehat dan target Block 7 berstatus `up`.

Blocker tersisa: Prometheus belum memiliki konfigurasi `alerting.alertmanagers`, dan belum tersedia receiver notification untuk menguji delivery, resolved notification, grouping, serta duplicate notification.

Mohon bantuan untuk:

1. Menentukan/deploy endpoint Alertmanager yang dapat dijangkau Prometheus Block 7.
2. Menyediakan receiver webhook test non-remediation.
3. Menentukan routing warning/critical, grouping, repeat interval, dan `send_resolved`.
4. Menentukan PIC serta window joint validation.

Dokumen detail dan acceptance criteria:
`task/task_tracker/ST-317_ALERTMANAGER_BLOCKER_HANDOFF.md`

Evidence teknis:
`implementation/dcim_ai_v2_rag/artifacts/st317/`

Setelah dependency tersedia, Block 7 akan menjalankan controlled firing/resolved test dan melengkapi evidence penutupan ST-317.

## 11. Related artifacts

- `task/task_tracker/ST-317_EXECUTION_REPORT.md`
- `implementation/dcim_ai_v2_rag/scripts/test_st317_prometheus_alerts.py`
- `implementation/dcim_ai_v2_rag/artifacts/st317/controlled-transition-results.json`
- `implementation/dcim_ai_v2_rag/k8s/prometheus-alert-rules.yaml`
- `prometheus_local/prometheus.yml`

# Template Prompt: Collecting Session Summary

Gunakan template ini untuk meminta AI agent membuat dokumen ringkasan dari sesi percakapan yang sedang berlangsung. Tujuannya adalah agar konteks dari sesi lama bisa dibawa ke sesi baru tanpa kehilangan informasi penting.

---

## Prompt Lengkap

```markdown
# PROMPT: Collecting Session Summary

Kamu adalah AI agent yang bertugas membuat dokumen ringkasan sesi percakapan yang sedang berlangsung.
Tujuan dokumen ini adalah menjadi **handoff context** untuk AI agent di sesi baru, agar agent berikutnya dapat melanjutkan pekerjaan tanpa kehilangan konteks, keputusan, preferensi user, progres, masalah, dan arah kerja.

Buat ringkasan dalam format Markdown yang padat, jelas, terstruktur, dan bisa langsung digunakan sebagai konteks awal pada sesi baru.

## Aturan Utama

1. Jangan menambahkan asumsi yang tidak disebutkan dalam percakapan.
2. Jangan membuat informasi palsu atau mengisi bagian kosong dengan karangan.
3. Bedakan antara fakta, asumsi, keputusan, dan hal yang masih perlu dikonfirmasi.
4. Fokus pada informasi yang berguna untuk melanjutkan pekerjaan.
5. Hilangkan percakapan kecil yang tidak relevan.
6. Simpan detail teknis, nama file, link, command, struktur, keputusan, error, dan constraint penting.
7. Gunakan bahasa yang ringkas, langsung, dan operasional.
8. Tulis seolah-olah dokumen ini akan dibaca oleh AI agent baru yang belum mengetahui sesi sebelumnya.
9. Jangan hanya merangkum isi chat, tapi susun ulang menjadi context handoff yang siap dipakai.
10. Prioritaskan akurasi dan kontinuitas kerja.

---

# SESSION SUMMARY DOCUMENT

## 1. Session Metadata

- **Session Title:** [Judul singkat sesi]
- **Date/Time:** [Tanggal sesi bila tersedia]
- **User:** [Nama user bila diketahui]
- **Main Topic:** [Topik utama sesi]
- **Session Type:** [Planning / Debugging / Writing / Research / Coding / Architecture / Review / Other]
- **Current Status:** [Completed / In Progress / Blocked / Needs Follow-up]

---

## 2. High-Level Summary

Tuliskan ringkasan singkat 3–7 kalimat tentang inti sesi ini.

Harus mencakup:

- Apa tujuan utama user.
- Apa yang sudah dikerjakan.
- Hasil atau keputusan utama.
- Kondisi terakhir sebelum sesi berakhir.

---

## 3. User Goal

Jelaskan tujuan user secara jelas.

Format:

- **Primary Goal:** [Tujuan utama user]
- **Secondary Goals:**
  - [Tujuan tambahan 1]
  - [Tujuan tambahan 2]
- **Expected Output:** [Output yang diinginkan user]
- **Success Criteria:** [Kriteria agar hasil dianggap berhasil]

---

## 4. Important Context

Catat semua konteks penting yang dibutuhkan agent baru.

Contoh konteks yang perlu disimpan:

- Latar belakang pekerjaan/proyek.
- Masalah yang sedang diselesaikan.
- Sistem, tools, stack, repo, file, atau environment yang digunakan.
- Kondisi khusus yang memengaruhi keputusan.
- Batasan teknis atau non-teknis.
- Preferensi user yang muncul selama sesi.

Format:

- **Background:** ...
- **Current Environment:** ...
- **Known Constraints:** ...
- **User Preferences:** ...
- **Important Notes:** ...

---

## 5. Key Decisions Made

Daftar keputusan penting yang sudah dibuat selama sesi.

Gunakan format tabel:

| Decision | Reason | Impact |
|---|---|---|
| [Keputusan] | [Alasan] | [Dampaknya untuk langkah berikutnya] |

Jangan masukkan ide yang belum diputuskan.

---

## 6. Work Completed

Tuliskan pekerjaan yang sudah selesai dilakukan dalam sesi ini.

Gunakan checklist:

- [x] [Pekerjaan selesai 1]
- [x] [Pekerjaan selesai 2]
- [x] [Pekerjaan selesai 3]

Sertakan hasil penting, struktur final, atau output yang sudah diberikan.

---

## 7. Current Progress / State

Jelaskan posisi terakhir pekerjaan.

Harus menjawab:

- Sudah sampai mana?
- Apa yang sedang dikerjakan saat sesi berhenti?
- Apa bagian yang belum selesai?
- Apakah ada file, draft, struktur, atau rencana terakhir yang harus dilanjutkan?

Format:

~~~text
Current state:
[Deskripsi kondisi terakhir secara jelas]
~~~

---

## 8. Open Issues / Unresolved Questions

Tuliskan hal yang belum selesai, belum pasti, atau perlu dikonfirmasi.

Format:

| Issue / Question | Status | Recommended Action |
|---|---|---|
| [Masalah/pertanyaan] | [Open / Pending / Blocked] | [Langkah yang disarankan] |

---

## 9. Next Recommended Actions

Berikan langkah lanjutan yang paling logis untuk agent berikutnya.

Urutkan berdasarkan prioritas.

1. [Langkah pertama]
2. [Langkah kedua]
3. [Langkah ketiga]
4. [Langkah berikutnya]

Setiap langkah harus actionable, bukan hanya arahan umum.

---

## 10. Files, Links, Artifacts, and References

Catat semua file, link, repo, dokumen, atau artifact yang disebutkan/digunakan.

Format:

| Item | Type | Purpose | Status |
|---|---|---|---|
| [Nama file/link] | [File/Repo/URL/Doc] | [Kegunaan] | [Used / Pending / Need Review] |

Bila tidak ada, tulis:

~~~text
No external files, links, or artifacts were used in this session.
~~~

---

## 11. Technical Details

Simpan detail teknis yang penting untuk dilanjutkan.

Gunakan hanya bila relevan.

### Commands Mentioned

~~~bash
[Command penting yang digunakan/dibahas]
~~~

### Config / Settings

~~~yaml
[Konfigurasi penting]
~~~

### Errors / Logs

~~~text
[Error, log, atau pesan masalah penting]
~~~

### Architecture / Structure

~~~text
[Struktur sistem, folder, workflow, atau arsitektur yang dibahas]
~~~

---

## 12. User Preferences and Working Style

Ringkas preferensi user yang muncul selama sesi dan berguna untuk sesi berikutnya.

Contoh:

- User suka jawaban ringkas tapi tetap lengkap.
- User tidak suka jawaban terlalu generik.
- User ingin hasil yang praktis dan langsung bisa digunakan.
- User mengutamakan struktur, detail, dan eksekusi nyata.
- User ingin jawaban yang tidak bluffing dan tidak terlalu AI-ish.

Format:

- **Tone Preference:** ...
- **Detail Level:** ...
- **Output Format Preference:** ...
- **Important Style Notes:** ...

---

## 13. Assumptions and Boundaries

Pisahkan asumsi dari fakta.

### Confirmed Facts

- [Fakta yang jelas dari percakapan]

### Assumptions

- [Asumsi yang dibuat, bila ada]

### Do Not Assume

- [Hal yang tidak boleh diasumsikan agent berikutnya]

---

## 14. Memory Candidates

Tuliskan informasi yang mungkin layak disimpan sebagai long-term memory, hanya bila benar-benar berguna untuk sesi berikutnya.

Format:

| Memory Candidate | Reason |
|---|---|
| [Informasi] | [Kenapa berguna] |

Bila tidak ada:

~~~text
No strong memory candidates identified.
~~~

---

## 15. Final Handoff Brief

Buat ringkasan akhir dalam 1 blok pendek yang bisa langsung ditempel ke sesi baru.

Format:

~~~markdown
The previous session focused on [topik]. The user wanted [tujuan]. We completed [hasil utama]. The current state is [kondisi terakhir]. The next agent should continue by [langkah berikutnya]. Important constraints/preferences: [constraint dan preferensi utama].
~~~

---

# Output Requirement

Hasil akhir wajib berupa Markdown dengan struktur di atas.
Jangan terlalu panjang, tapi jangan menghilangkan konteks penting.
Prioritaskan informasi yang membantu agent berikutnya langsung melanjutkan pekerjaan.
```

---

## Prompt Versi Singkat

```markdown
Buatkan SESSION SUMMARY dari percakapan ini sebagai handoff context untuk AI agent di sesi baru.

Ringkasan harus:

- Akurat, padat, dan tidak mengarang.
- Menjelaskan tujuan user, konteks penting, progres, keputusan, hasil kerja, masalah terbuka, file/link/artifact, detail teknis, preferensi user, dan next action.
- Ditulis dalam Markdown.
- Dibuat agar agent baru bisa langsung melanjutkan pekerjaan tanpa membaca seluruh chat lama.

Gunakan struktur berikut:

# Session Summary

## 1. High-Level Summary
[Ringkasan 3–7 kalimat]

## 2. User Goal
- Primary goal:
- Expected output:
- Success criteria:

## 3. Important Context
- Background:
- Constraints:
- Tools/files/systems involved:
- User preferences:

## 4. Key Decisions
| Decision | Reason | Impact |
|---|---|---|

## 5. Work Completed
- [x] ...

## 6. Current State
[Posisi terakhir pekerjaan]

## 7. Open Issues
| Issue | Status | Recommended Action |
|---|---|---|

## 8. Next Actions
1. ...
2. ...
3. ...

## 9. Files / Links / Artifacts
| Item | Purpose | Status |
|---|---|---|

## 10. Technical Notes
~~~text
Commands, configs, logs, architecture, or important implementation notes.
~~~

## 11. User Working Style
- Tone:
- Detail level:
- Output preference:
- Things to avoid:

## 12. Final Handoff Brief
[Paragraf pendek yang bisa langsung ditempel ke sesi baru]
```

---

## Rekomendasi Penggunaan

- Gunakan **Prompt Lengkap** untuk sesi panjang, kompleks, teknis, atau banyak keputusan.
- Gunakan **Prompt Versi Singkat** untuk sesi ringan atau ketika hanya butuh context handoff cepat.
- Tempelkan prompt ini di akhir sesi lama, lalu hasil ringkasannya dipakai sebagai input awal di sesi baru.

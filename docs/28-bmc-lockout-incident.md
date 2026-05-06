# Dokumen Insiden: BMC (Lenovo XClarity Controller 2) Account Lockout

## 1. Deskripsi Masalah
Akun `hndept` pada BMC (Lenovo XClarity Controller 2 / XCC2) saat ini berstatus **terkunci (locked out)** dengan pesan error: *"Too many unsuccessful login attempts. You have currently been locked."* 

Masalah ini disebabkan oleh adanya skrip otomatisasi telemetri (*poller*) DCIM yang berjalan di *background*. Skrip ini terus-menerus mencoba melakukan autentikasi ke REST API Redfish milik BMC menggunakan *credential* (kata sandi) yang salah, usang, atau sudah diubah.

## 2. Penyebab Dasar (Root Cause)
Sistem observabilitas DCIM memiliki beberapa skrip Python yang bertugas mengambil metrik perangkat keras (suhu, status kipas, kesehatan komponen) secara periodik. Skrip tersebut melakukan permintaan HTTP GET ke beberapa *endpoints* Redfish secara berurutan.

Setiap kali skrip berjalan dengan kata sandi yang salah, XCC2 akan langsung mencatat 3 kegagalan login secara bersamaan (karena skrip mencoba menarik data dari `Systems`, `Chassis`, dan `Managers`). Hal ini memicu **Security Policy: Account Lockout** bawaan dari Lenovo XCC2 yang memblokir akun secara instan setelah sekian kali percobaan gagal (biasanya batas maksimalnya hanya 3 hingga 5 kali gagal).

## 3. Bukti Konfigurasi yang Memicu Masalah
Terdapat dua skrip di direktori `/home/infra/dcim_metrics_project/scripts/` yang secara aktif melakukan *polling* ke deretan IP Server Lenovo (10.50.0.x) dengan kredensial statis. 

**A. Skrip `dcim_inventory_poller.py` (Baris 38-40)**
Skrip poller utama ini mengambil kredensial lewat sistem *environment variable* dengan *fallback* statis:
```python
REDFISH_SERVERS = ["10.50.0.2", "10.50.0.3", "10.50.0.4", "10.50.0.5", "10.50.0.6"]
REDFISH_USER = os.getenv("REDFISH_USER", "hndept")
REDFISH_PASS = os.getenv("REDFISH_PASS", "F!tech@0918")
```

**B. Skrip `redfish_inventory_poller.py` (Baris 8-10, 21, 38, 51)**
Skrip ini juga mengandung kredensial statis dan menunjukkan mengapa blokir terjadi sangat cepat. Dalam satu iterasi per server, ada 3 permintaan autentikasi *Basic Auth* yang dieksekusi:
```python
SERVERS = ["10.50.0.2", "10.50.0.3", "10.50.0.4", "10.50.0.5", "10.50.0.6"]
USER = "hndept"
PASS = "F!tech@0918"

# Pemanggilan API (3 kali berturut-turut per server):
r = requests.get(f"https://{ip}/redfish/v1/Systems/1", auth=(USER, PASS), verify=False, timeout=2)
r = requests.get(f"https://{ip}/redfish/v1/Chassis/1", auth=(USER, PASS), verify=False, timeout=2)
r = requests.get(f"https://{ip}/redfish/v1/Managers/1", auth=(USER, PASS), verify=False, timeout=2)
```

Karena skrip ini biasanya dipanggil setiap 10-60 detik oleh sistem Telegraf, maka jika `F!tech@0918` bukan lagi *password* yang benar untuk akun `hndept`, Lenovo XCC2 akan diserang dengan puluhan login gagal setiap menitnya, sehingga memicu blokir pengamanan (*lockout*).

## 4. Solusi & Langkah Perbaikan
Untuk memulihkan keadaan, Anda harus melakukan langkah-langkah berikut secara berurutan:

1. **Hentikan *Spam* Autentikasi (Stop Poller)**: 
   Matikan sementara layanan Telegraf yang mengeksekusi skrip ini agar tidak terus-menerus mencoba login.
   ```bash
   sudo systemctl stop telegraf
   ```
2. **Buka Kunci (Unlock) Akun BMC**: 
   - Login ke Web GUI Lenovo XCC2 menggunakan akun administrator lain (misalnya `USERID` atau `admin`).
   - Masuk ke menu navigasi **BMC Configuration -> User/LDAP**.
   - Pilih baris akun `hndept`.
   - Lakukan tindakan **Unlock** atau *Reset Lockout Status*.
3. **Perbarui Kata Sandi di Skrip**: 
   Setelah Anda mengetahui kata sandi `hndept` yang *sebenarnya*, perbarui kata sandi tersebut ke dalam *environment variables* server atau langsung ke dalam *file* Python di atas (mengganti tulisan `F!tech@0918`).
4. **Jalankan Kembali Poller**: 
   Setelah konfigurasi sinkron, aktifkan kembali layanan telemetrinya.
   ```bash
   sudo systemctl start telegraf
   ```

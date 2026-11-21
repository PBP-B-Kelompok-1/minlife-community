# Announcement API - Mobile Checkpoint 1

Pemilik modul: **Enzo Susilo - 2506584382**.

API ini berada di repo **web Django** `minlife-community`. Aplikasi Flutter berada
di repo terpisah dan akan mengakses backend yang sama. Database announcement tidak
disalin ke aplikasi mobile.

## Status dan scope

- Implementasi lokal: serializer DRF, endpoint CRUD, search/sort/pagination,
  capabilities, dan subscribe/unsubscribe Firebase Installation ID (FID).
- Endpoint baru mengikuti prefix `/api/v1/` dan SessionAuthentication API Weekly
  Challenge. Endpoint HTML/HTMX dan JSON legacy masih tersedia.
- Pembuatan announcement melalui API menjadwalkan pengiriman push setelah commit;
  update/delete tidak mengirim push baru. Firebase gagal tidak membatalkan penyimpanan.
- Deployment API ke PWS, smoke test Firebase nyata setelah deployment, dan integrasi
  Flutter masih harus diverifikasi. Halaman, navigasi, dan README Flutter dikerjakan
  di repo Flutter, bukan dibuktikan oleh perubahan backend ini.

## Base URL dan endpoint

Lokal: `http://127.0.0.1:8000/api/v1/announcements/`.

Target PWS setelah deployment:
`https://clement-kevin-minlifecommunity.pws.cs.ui.ac.id/api/v1/announcements/`.
URL target ini bukan pernyataan bahwa versi ini sudah dideploy.

Semua endpoint baru memakai trailing slash.

| Method | Path relatif | Akses | Respons sukses |
| --- | --- | --- | --- |
| GET | (base URL) | Publik | 200 paginated list |
| POST | (base URL) | `announcements.add_announcement` | 201 objek baru |
| GET | `<uuid>/` | Publik | 200 objek detail |
| PUT | `<uuid>/` | `announcements.change_announcement` | 200 objek hasil edit |
| PATCH | `<uuid>/` | `announcements.change_announcement` | 200 objek hasil edit parsial |
| DELETE | `<uuid>/` | `announcements.delete_announcement` | 204 tanpa body |
| GET | `capabilities/` | Publik | 200 capabilities user saat ini |
| POST | `notifications/subscribe/` | Login | 201 subscription baru / 200 sudah ada |
| POST | `notifications/unsubscribe/` | Login | 200, termasuk bila subscription sudah tidak ada |

Tidak cukup hanya menyembunyikan tombol moderator: server memeriksa model permission
pada setiap request write. User login biasa dapat subscribe/unsubscribe tetapi tidak
otomatis mendapat hak CRUD announcement.

## Kontrak JSON

Contoh list, dengan nilai ID/tanggal ilustratif:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "980819cd-b875-4230-b117-670fdf349085",
      "title": "Community clean-up",
      "content": "Join us this Saturday.",
      "created_by": {
        "id": "953774ac-27fd-494c-899e-9d61ab9809f5",
        "username": "moderator"
      },
      "created_at": "2026-11-20T19:00:00+07:00",
      "created_at_display": "20 Nov 2026",
      "updated_at": "2026-11-20T19:00:00+07:00"
    }
  ]
}
```

`GET <uuid>/`, `POST`, `PUT`, dan `PATCH` mengembalikan objek announcement langsung,
tanpa pembungkus `data` atau `results`. `created_by` bisa `null` bila creator dihapus.
`created_at` dan `updated_at` adalah ISO 8601; gunakan parsing tanggal pada Flutter.
`content` berupa teks biasa.

Query list:

- `q`: pencarian case-insensitive pada title atau content, whitespace luar dibuang.
- `sort=newest` (default) atau `sort=oldest`; nilai lain kembali ke newest.
- `page=1` (default).
- `page_size=10` (default), maksimum 50.
- Hasil kosong: `count: 0`, `results: []`; halaman tidak tersedia menghasilkan 404.

Payload create atau PUT:

```json
{"title": "Community clean-up", "content": "Join us this Saturday."}
```

Keduanya wajib untuk POST/PUT; PATCH cukup mengirim field yang berubah. Title maksimum
255 karakter. Title/content tidak boleh null, kosong, atau hanya whitespace.
ID, creator, dan timestamps read-only: server mengabaikan nilai yang dikirim client
dan mengambil creator dari session. Edit mempertahankan creator dan created_at.

Contoh validasi 400:

```json
{"title": ["This field may not be blank."]}
```

Error permission/CSRF (403), objek tidak ditemukan (404), metode tidak didukung (405),
atau JSON rusak (400) menggunakan objek `detail`. Pemeriksaan autentikasi/permission
dapat terjadi sebelum pemeriksaan metode atau lookup objek. Request JSON sebaiknya
mengirim `Accept: application/json` dan `Content-Type: application/json`.

Capabilities untuk guest/user biasa:

```json
{"can_create": false, "can_change": false, "can_delete": false}
```

Nilai mengikuti permission user saat ini. Flutter dapat menggunakannya untuk menentukan
tombol yang ditampilkan; backend tetap menjadi sumber pemeriksaan izin.

## Autentikasi dan CSRF

API menggunakan **session Django**, sama seperti API Weekly Challenge. Cookie `sessionid`
menentukan identitas user. Request POST/PUT/PATCH/DELETE dari session terautentikasi
juga harus menyertakan cookie `csrftoken` dan header `X-CSRFToken` yang cocok.
Cookie/token tidak boleh ditulis di source code atau README.

Untuk pengecekan browser lokal, login melalui `/login`, lalu buka API pada host yang sama
(jangan mencampur `localhost` dan `127.0.0.1`). DRF browsable API mendukung form request.
Login HTML existing tetap tersedia; endpoint login JSON khusus Flutter belum dibuat
oleh perubahan modul ini. Koordinasikan login, cookie storage, dan CSRF dengan pemilik
modul User sebelum menghubungkan write dari Flutter. CSRF harus diperbarui setelah
login jika token dirotasi. Jangan mengatasi 403 dengan menonaktifkan CSRF.

## Notifications

Kedua endpoint subscription menerima payload:

```json
{"installation_id": "FID_DARI_FIREBASE_SDK"}
```

- FID wajib string nonblank, maksimum 255 karakter, whitespace luar dibuang.
- Backend memvalidasi bentuk input dan menyimpan FID; keberhasilan subscribe bukan
  bukti bahwa izin perangkat atau pengiriman FCM nyata sudah berhasil.
- Subscribe mengembalikan `{"subscribed": true}`; pengulangan tidak membuat duplikat.
- Satu FID terhubung ke satu user aktif, mengikuti perilaku web existing. Subscribe
  setelah ganti akun memindahkan kepemilikan perangkat ke user session saat ini.
- Unsubscribe mengembalikan `{"subscribed": false}` dan hanya menghapus subscription
  milik user saat ini. Logout/opt-out di Flutter harus mengurus lifecycle ini.
- Pengiriman memakai konfigurasi Firebase server existing. Creator dikecualikan,
  pengiriman dibatch, dan subscription tidak terdaftar dibersihkan oleh sender.
- Payload push existing mempunyai `announcement_id` dan `announcement_url`.
  Flutter perlu memakai ID untuk membuka halaman detail di aplikasinya. URL tetap
  menunjuk detail web agar klik notifikasi browser existing berfungsi.
- Firebase SDK Flutter harus menggunakan mekanisme registrasi yang kompatibel dengan
  backend FID ini. Jangan mengirim legacy registration token ke field FID tanpa
  menyesuaikan kontrak dan sender.

## Alur Flutter ke Django/PWS

```text
Halaman Flutter -> service HTTP asinkron -> API DRF PWS -> database Django
JSON respons -> model Dart -> state loading/success/empty/error -> widget
Form moderator -> session + CSRF -> serializer/permission DRF -> database
Create tersimpan -> on_commit -> FCM -> perangkat -> buka detail berdasarkan ID
```

Simpan base URL di konfigurasi aplikasi. Parser list membaca `results`, sedangkan parser
detail membaca objek langsung. DELETE sukses 204 tidak memiliki JSON untuk di-decode.
Tangani error field 400, permission/session/CSRF 403, dan detail/page 404.

## Menjalankan dan memverifikasi

Jalankan dari root repo web di PowerShell:

```powershell
.\env\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test announcements
python manage.py runserver
```

API ini tidak mengubah model dan tidak membutuhkan migration baru. `migrate` tetap
diperlukan saat menyiapkan clone/deployment yang belum memiliki migration kelompok.

Untuk smoke test CRUD lokal tanpa mengirim push ke subscriber sungguhan, set
`$env:FIREBASE_PUSH_ENABLED = 'FALSE'` di terminal sebelum menjalankan server. Pengaturan
ini berlaku pada proses terminal tersebut. Untuk tes push nyata, hentikan server,
aktifkan lagi flag sesuai konfigurasi Firebase, lalu jalankan ulang server.

Request read sederhana dari terminal lain:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/announcements/?sort=newest&page_size=10'
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/announcements/capabilities/'
```

Checklist manual (lokal sebelum PR; PWS setelah deployment):

- [ ] Guest: list/detail/search/sort berjalan; create ditolak JSON 403.
- [ ] Moderator: create/edit/delete dari browsable API pada session yang sama.
- [ ] Create dari API terlihat di halaman web; edit web terlihat di GET API.
- [ ] Title/content kosong ditolak; PATCH mempertahankan created_at.
- [ ] User biasa tidak dapat CRUD; hanya subscription miliknya yang bisa dihapus.
- [ ] Setelah deployment: ulangi read/write pada PWS, bukan hanya localhost.
- [ ] Dengan akun penerima dan FID nyata: create oleh moderator menghasilkan push;
      creator tidak menerima push sendiri. Jangan memakai FID contoh untuk tes ini.

## Hasil verifikasi lokal - 20 November 2026

| Pemeriksaan | Hasil |
| --- | --- |
| Baseline `python manage.py test announcements` sebelum penambahan API | 70/70 lulus |
| `python manage.py test announcements.tests_api --noinput` | 26/26 lulus |
| `python manage.py test --noinput` setelah implementasi | 338/338 lulus, termasuk test web dan API baru |
| `python manage.py check` | Tidak ada issue |
| `python manage.py makemigrations --check --dry-run` | No changes detected |
| `python -m pip check` | No broken requirements found |
| HTTP lokal list / detail / capabilities guest | Semua 200; list membaca 43 record existing; capabilities guest semua false |
| HTTP lokal halaman web announcement | 200 HTML |

Lingkungan verifikasi memakai Django 5.2.17 dan DRF 3.18.3 sesuai dependency tim.
Suite lengkap selesai dalam 422.427 detik. Ada warning direktori `staticfiles/`
belum tersedia pada lingkungan lokal; tidak menyebabkan kegagalan test. Server
sementara untuk smoke test HTTP dihentikan setelah selesai. Pengujian HTTP tersebut
hanya membaca data; pengujian write otomatis memakai test database terpisah.

## Checkpoint 1 dan Git

Branch backend: `feat/announcements-drf`, berbasis `dev`. Semua perubahan ini masuk
repo web. Branch ini tidak perlu dibuat ulang bila sudah aktif.

Saran commit setelah pemeriksaan berhasil (periksa `git diff` dan staged diff dahulu):

1. `feat(announcements): add versioned DRF API and notification subscriptions`
2. `test(announcements): cover DRF CRUD permissions sessions and notifications`
3. `docs(announcements): document mobile API and checkpoint handoff`

PR dibuat setelah implementasi, test, dan dokumen masuk branch ini, menuju `dev`.
Isi PR mencakup perubahan, hasil tes, dan pekerjaan manual/deployment yang belum
dilakukan. Minta peer review sesuai Git flow kelompok. Jika mengejar rubrik Git
tertinggi, sertakan AI review PR sesuai proses tim. GitHub CI bukan deployment PWS;
workflow repo saat ini menyebut deployment PWS masih manual.

Untuk kelengkapan Checkpoint 1 kelompok, masih harus dikerjakan di **repo Flutter**:

- [ ] Halaman Announcement dan navigasi menuju halaman tersebut.
- [ ] README: anggota/NPM, deskripsi, scope/pembagian modul, aktor, dan alur DRF/PWS.
- [ ] Salin kontrak endpoint yang benar dan tulis status integrasi secara jujur.
- [ ] Integrasi list API dianjurkan; seluruh integrasi widget/CRUD harus selesai saat final.
- [ ] Tautan repo Flutter dikumpulkan ke SCELE. Figma/APK boleh menyusul Checkpoint 1.

## Penggunaan AI dan batas verifikasi

Codex membantu inspeksi basis dev dan pola Weekly Challenge, implementasi serializer,
permission dan view DRF, test API, serta dokumentasi. Strategi instruksi: lanjutkan
modul announcement existing, ikuti pola API tim, pertahankan perilaku web, verifikasi
session/CSRF dan failure Firebase, lalu pisahkan hasil lokal dari pekerjaan Flutter/PWS.

Koreksi selama verifikasi: test awal mengharapkan 405 untuk metode tidak didukung
dari guest, tetapi permission DRF lebih dahulu menghasilkan 403. Test diperbaiki agar
menguji 405 dengan moderator; proteksi permission tetap dipertahankan.

Tes push API menggunakan mock untuk memeriksa scheduling dan penanganan kegagalan;
itu tidak membuktikan pengiriman Firebase nyata. Pemeriksaan manual, peer review,
deployment PWS, dan demonstrasi Flutter perlu dilakukan pemilik modul/kelompok.
Hasil otomatis dicatat pada bagian Hasil verifikasi lokal di atas.

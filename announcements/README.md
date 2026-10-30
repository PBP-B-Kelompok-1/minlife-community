# Announcements & Notifications

Modul ini menyediakan pengumuman resmi untuk komunitas Minlife. Halaman list dan detail
dapat dibaca publik, sedangkan Create, Update, dan Delete hanya tersedia bagi moderator
atau user yang mempunyai Django model permission terkait. User yang login dapat memilih
untuk menerima system notification melalui Firebase Cloud Messaging (FCM).

## Fitur

- List dan detail announcement yang responsif untuk desktop dan mobile.
- Tanggal yang ditampilkan berasal dari `created_at` dan tidak berubah ketika diedit.
- Search judul atau isi menggunakan Django ORM `icontains`.
- Sorting Newest/Oldest menggunakan `created_at` di database.
- Create, Update, dan Delete dengan `ModelForm` serta authorization server-side.
- Read dan CRUD dinamis menggunakan HTMX tanpa full-page reload.
- Halaman HTML biasa tetap tersedia sebagai fallback ketika HTMX tidak digunakan.
- Endpoint JSON untuk list dan detail.
- Opt-in/opt-out push notification per browser.
- System notification pada foreground maupun background.
- Klik notifikasi membuka detail announcement terkait.

## Model

### `Announcement`

| Field | Konfigurasi | Keterangan |
| --- | --- | --- |
| `id` | UUID primary key | Identifier announcement. |
| `created_by` | `ForeignKey`, `SET_NULL` | Creator dipertahankan secara nullable jika user dihapus. |
| `title` | `CharField(255)` | Judul wajib. |
| `content` | `TextField` | Isi wajib. |
| `created_at` | `auto_now_add`, indexed | Waktu pembuatan dan dasar sorting. |
| `updated_at` | `auto_now` | Waktu perubahan terakhir. |

Default ordering adalah `-created_at` lalu `-id` agar hasil terbaru muncul dahulu dan
tetap deterministik ketika timestamp sama.

### `FCMSubscription`

Model ini menghubungkan satu browser/device dengan user melalui Firebase Installation
ID. Satu user dapat mempunyai beberapa subscription, sedangkan satu Installation ID
hanya dapat dimiliki satu user aktif. Subscription dihapus ketika user dihapus.

## URL dan Endpoint

| Method | URL | Akses | Fungsi |
| --- | --- | --- | --- |
| `GET` | `/announcements/` | Publik | List, search, dan sorting. |
| `GET/POST` | `/announcements/create/` | Permission add | Membuat announcement. |
| `GET` | `/announcements/<uuid>/` | Publik | Detail announcement. |
| `GET/POST` | `/announcements/<uuid>/edit/` | Permission change | Mengubah announcement. |
| `GET/POST` | `/announcements/<uuid>/delete/` | Permission delete | Konfirmasi dan menghapus announcement. |
| `POST` | `/announcements/notifications/subscribe/` | Login | Menyimpan Installation ID. |
| `POST` | `/announcements/notifications/unsubscribe/` | Login | Menghapus Installation ID milik user. |
| `GET` | `/firebase-messaging-sw.js` | Publik | Root-scoped Firebase service worker. |
| `GET` | `/api/announcements` | Publik | JSON list dengan search/sort. |
| `GET` | `/api/announcement/<uuid>` | Publik | JSON detail. |

## Authorization

CRUD memakai permission bawaan model Django:

- `announcements.add_announcement`
- `announcements.change_announcement`
- `announcements.delete_announcement`

Kontrol moderator disembunyikan dari user biasa, tetapi perlindungan utama tetap berada
di view. Creator selalu diambil dari `request.user`; field creator dari payload tidak
dipercaya. Form hanya mengekspos `title` dan `content`.

## Interaktivitas HTMX

Search mengirim request setelah debounce 300 ms dan sorting mengirim request ketika
pilihan berubah. Detail, Show less, dan CRUD menukar fragment `_results.html` dengan
`outerHTML`. URL diperbarui melalui `hx-push-url` agar navigasi Back/Forward tetap
berfungsi.

Create/Edit/Delete memakai native `<dialog>`. Request biasa tetap merender halaman form
atau confirmation penuh; request HTMX hanya merender partial ke dialog. Submit berhasil
memakai `HX-Retarget`, `HX-Reswap`, dan `HX-Trigger` untuk memperbarui list, menutup
dialog, dan menampilkan shared toast kelompok.

## Alur Push Notification

```text
Moderator membuat announcement
        -> Django menyimpan ke database
        -> transaction.on_commit
        -> Firebase Admin mengirim multicast message
        -> FCM mengirim ke browser yang berlangganan
        -> service worker menampilkan system notification
        -> klik notification membuka detail announcement
```

Keputusan penting:

- Creator dikecualikan agar tidak menerima notifikasi buatannya sendiri.
- Pesan dikirim dalam batch maksimal 500 Installation ID.
- Installation ID yang tidak lagi terdaftar dibersihkan dari database.
- Error Firebase dicatat tetapi tidak membatalkan announcement yang sudah tersimpan.
- Foreground message tetap ditampilkan sebagai system notification, bukan toast isi
  announcement di halaman.
- Subscription dan permission tersimpan per origin serta browser. User perlu Enable
  kembali ketika berpindah dari localhost ke PWS.

HTMX tidak menggantikan JavaScript FCM. HTMX menangani request dan DOM swap ketika
halaman aktif, sedangkan service worker diperlukan untuk menerima push saat halaman
berada di background atau tertutup.

## Konfigurasi Firebase

Environment variables client yang dibaca Django:

```text
FIREBASE_API_KEY
FIREBASE_AUTH_DOMAIN
FIREBASE_PROJECT_ID
FIREBASE_STORAGE_BUCKET
FIREBASE_MESSAGING_SENDER_ID
FIREBASE_APP_ID
FIREBASE_VAPID_KEY
FIREBASE_PUSH_ENABLED
```

Credential server menggunakan salah satu opsi berikut:

- Lokal: `GOOGLE_APPLICATION_CREDENTIALS` berisi path JSON service account.
- PWS: `FIREBASE_SERVICE_ACCOUNT_B64` berisi JSON service account yang di-encode Base64.

Jangan commit `.env`, service-account JSON, password database, atau nilai
`FIREBASE_SERVICE_ACCOUNT_B64`.

## Menjalankan Secara Lokal

```powershell
.\env\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py tailwind build
python manage.py runserver
```

Buka `/announcements/`, login, lalu tekan **Enable Notifications**. Permission dan
subscription localhost tidak otomatis berlaku pada origin PWS.

## Testing

```powershell
python manage.py test announcements
python manage.py test announcements.tests.FCMWebClientTests announcements.tests.AnnouncementNotificationSendTests
python manage.py check
python manage.py makemigrations --check --dry-run
```

Hasil verifikasi final:

- 70/70 test Announcements lulus.
- 14 test FCM client/server terfokus lulus.
- Django system check tidak menemukan issue.
- Tidak ada perubahan model setelah migration `0002_fcmsubscription`.
- Real Firebase send dan system-notification smoke test dua browser berhasil.
- Creator tidak menerima push buatannya sendiri dan klik notifikasi membuka detail.

## Deployment

- Jalankan migration `announcements.0002_fcmsubscription` pada database PWS.
- Pastikan CSS Tailwind sudah dibangun sebelum `collectstatic`, atau commit compiled CSS
  sesuai strategi deployment kelompok.
- Simpan seluruh konfigurasi Firebase pada PWS Environs, bukan source code.
- Setelah deployment HTTPS, Enable Notifications kembali pada browser/device penerima.
- Verifikasi `/firebase-messaging-sw.js`, request subscribe berstatus 200, dan push dari
  akun moderator berbeda.

## Penggunaan AI

OpenAI Codex digunakan untuk membantu audit referensi, penyusunan test, implementasi
Django/HTMX/FCM, debugging, dan dokumentasi. Developer menentukan kebutuhan produk,
menyiapkan Firebase dan environment, menjalankan migration/test, melakukan smoke test
dua akun/browser, mereview perubahan, serta menangani Git flow dan deployment.

Riwayat checkpoint, hasil Red/Green, koreksi, limitasi, dan commit lengkap disimpan pada
[`IMPLEMENTATION_LOG.md`](IMPLEMENTATION_LOG.md).

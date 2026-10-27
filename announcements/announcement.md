# Announcements

## Tujuan Modul

Modul Announcements menyediakan pengumuman resmi komunitas Minlife. Pengumuman dapat
dibaca oleh pengguna umum, sedangkan operasi create, update, dan delete akan dibatasi
untuk pengguna yang mempunyai Django model permissions yang sesuai.

Checkpoint 1 mencakup model data, migration awal, dan unit test model. Checkpoint 2
menambahkan public Read berupa list/detail HTML, endpoint JSON, database search, dan
sorting. Checkpoint 3 menambahkan Create server-rendered dengan `ModelForm` dan
authorization berbasis Django permission. Update/delete, interaktivitas tanpa reload,
integrasi frontpage, dan Firebase Cloud Messaging belum diimplementasikan.

## Arsitektur Django MVT

- **Model:** `Announcement` sudah diimplementasikan pada `models.py`.
- **View:** list/detail HTML, list/detail JSON, dan Create sudah diimplementasikan.
- **Template:** `templates/announcements/list.html` menyediakan server-rendered baseline
  yang responsif dan mengikuti pola list/detail Figma.
- **URL:** HTML tersedia di `/announcements/`; endpoint data tersedia di
  `/api/announcements` dan `/api/announcement/<uuid>`.
- **Form:** `AnnouncementForm` untuk Create hanya mengekspos title dan content. Form yang
  sama direncanakan untuk Edit pada checkpoint berikutnya.

## Model dan Relasi Data

Model `Announcement` memiliki field berikut:

| Field | Tipe | Tujuan |
| --- | --- | --- |
| `id` | `UUIDField` | Primary key yang tidak mudah ditebak dan konsisten dengan pola repository. |
| `created_by` | `ForeignKey` | Menghubungkan pengumuman dengan custom User melalui `settings.AUTH_USER_MODEL`. |
| `title` | `CharField(max_length=255)` | Judul wajib pengumuman. |
| `content` | `TextField` | Isi wajib pengumuman. |
| `created_at` | `DateTimeField(auto_now_add=True)` | Waktu pembuatan yang tidak berubah saat diedit. |
| `updated_at` | `DateTimeField(auto_now=True)` | Waktu perubahan terakhir. |

`created_by` menggunakan `SET_NULL` dan `null=True`. Pengumuman dirancang tetap ada
ketika akun pembuatnya dihapus. Reverse relation pada User adalah
`created_announcements`.

`created_at` diberi database index karena akan digunakan untuk sorting. Default
ordering adalah `-created_at` lalu `-id`, sehingga pengumuman terbaru muncul dahulu dan
hasil tetap deterministik ketika timestamp sama.

Image, event date, published date, category, dan notification data tidak dimasukkan ke
migration awal karena belum diperlukan pada core model.

## Read, Search, dan Sorting

Halaman list dan detail dapat dibaca tanpa login. Search menerima parameter GET `q` dan
mencari title atau content melalui `Q(...__icontains=...)` pada Django ORM. Nilai search
di-trim sebelum dipakai.

Sorting menerima allowlist berikut:

- `newest`: `-created_at`, lalu `-id`.
- `oldest`: `created_at`, lalu `id`.

Nilai sort yang tidak dikenal dikembalikan ke `newest`; input pengguna tidak pernah
dimasukkan langsung ke `order_by()`. HTML dan JSON memakai helper QuerySet yang sama agar
filtering tidak terduplikasi atau hanya dilakukan di browser.

JSON menampilkan UUID, title, content, timestamp ISO berdasarkan timezone Django, dan
`created_at_display` dengan format seperti `12 Oct 2026`.

## Authentication dan Authorization

Public Read tidak membutuhkan login. Create memerlukan autentikasi dan permission
`announcements.add_announcement`. Guest diarahkan ke login, sedangkan user yang sudah
login tetapi tidak mempunyai permission menerima respons 403.

Group `Moderator` menggunakan Django permissions yang sudah diprovision oleh migration:

- `announcements.add_announcement`
- `announcements.change_announcement`
- `announcements.delete_announcement`

View nantinya wajib memeriksa permission pada server. Menyembunyikan tombol di template
hanya akan menjadi perlindungan UX, bukan pengganti authorization server-side.

Create view sudah mengikuti aturan tersebut. Tombol Add hanya dirender ketika
`request.user.has_perm("announcements.add_announcement")` bernilai benar, dan endpoint
tetap melakukan pemeriksaan permission secara independen. `created_by` selalu ditetapkan
dari `request.user`; nilai creator yang dikirim melalui POST diabaikan.

## Interaktivitas

Keputusan Fetch API, HTMX, atau hybrid berstatus **pending**. Checkpoint 2 menggunakan
form GET dan server-rendered HTML sebagai baseline yang tetap berfungsi tanpa JavaScript.
Checkpoint 3 menambahkan form POST server-rendered dengan CSRF protection dan error
validation. Belum ada AJAX atau HTMX; modal Create responsif akan menjadi progressive
enhancement pada checkpoint interaktivitas.

## Testing Checkpoint 1

Unit test model mencakup:

- UUID dan konfigurasi field penting.
- Validasi bahwa title dan content wajib.
- Representasi string menggunakan title.
- Reverse relation dari User.
- Konfigurasi `null=True` dan `on_delete=SET_NULL` untuk creator.
- `created_at` tetap saat edit dan `updated_at` diperbarui.
- Default ordering terbaru dahulu.

Hasil aktual:

- Fase Red: import `Announcement` gagal karena model belum tersedia; terverifikasi.
- Migration `announcements.0001_initial` dibuat dan diterapkan secara manual oleh
  developer pada database development; hasil `OK`.
- Percobaan Green pertama: 6 test lulus dan 1 error akibat tabel
  `weeklychallenge_challengesubmission` tidak tersedia pada database test.
- Test diisolasi agar memeriksa konfigurasi relasi Announcement tanpa bergantung pada
  schema modul Weekly Challenge milik anggota lain.
- Percobaan Green kedua: 7 test dijalankan dan seluruhnya lulus dalam 7.637 detik.
- Django system check: 0 issue.
- Database test in-memory dibuat dan dihancurkan dengan sukses.
- Coverage belum diukur; developer memilih tidak menjalankan pengukuran coverage pada
  checkpoint ini untuk menjaga proses tetap proporsional. Tidak ada angka coverage yang
  diklaim.

Keterbatasan: perilaku penghapusan User secara end-to-end belum diuji karena app
Weekly Challenge memiliki model yang berelasi dengan User tetapi belum mempunyai
migration awal. Konfigurasi `SET_NULL` Announcement tetap diuji melalui metadata field
dan kemampuan menyimpan `created_by=None`.

## Testing Checkpoint 2

Test Read mencakup:

- Akses publik untuk list dan detail.
- Template dan default ordering Newest.
- Empty state dan detail 404.
- Search title/content yang case-insensitive.
- Sorting Oldest dan fallback untuk nilai sort tidak valid.
- Struktur data JSON list/detail.
- Search/sort pada endpoint JSON.
- Penolakan request selain GET.

Hasil aktual:

- Fase Red: 10/10 test error karena namespace HTML dan endpoint API belum tersedia;
  penyebab sesuai fitur yang belum diimplementasikan.
- Green terfokus: 10/10 test Read lulus dalam 11.027 detik.
- Regresi app: seluruh 17/17 test Announcements lulus dalam 15.576 detik.
- Django system check: 0 issue.
- Smoke test development server untuk halaman HTML dan endpoint JSON dinyatakan sesuai
  oleh developer.
- Peringatan folder `staticfiles` belum tersedia muncul saat test, tetapi tidak
  menyebabkan kegagalan dan bukan berasal dari modul Announcements.
- Coverage belum diukur dan tidak ada angka coverage yang diklaim.

## Keputusan Teknis Checkpoint 1

- Menggunakan `settings.AUTH_USER_MODEL` agar relasi mengikuti custom User project dan
  migration memakai swappable dependency.
- Menggunakan UUID agar konsisten dengan model utama lain di repository.
- Menggunakan `SET_NULL` untuk mempertahankan pengumuman ketika creator tidak tersedia.
- Tidak menambahkan constraint, dependency, atau abstraction yang belum diperlukan.
- Tidak mengubah modul anggota lain untuk memperbaiki masalah migration Weekly Challenge.
- Tidak melakukan refactor tambahan karena implementasi model sudah minimum dan jelas.

## Testing Checkpoint 3

Test Create dan authorization mencakup:

- `AnnouncementForm` hanya mengekspos title/content dan memvalidasi field wajib.
- Guest diarahkan ke halaman login.
- User biasa menerima 403 untuk GET dan POST serta tidak dapat membuat data.
- Moderator dapat membuka form dan membuat announcement.
- Superuser dapat membuat announcement.
- Creator tidak dapat dipalsukan dari payload POST.
- Invalid form dirender ulang tanpa membuat data.
- Tombol Add hanya muncul untuk user dengan permission.
- Method selain GET/POST ditolak.

Hasil aktual:

- Fase Red: 10/10 test error karena `forms.py` dan route Create belum tersedia;
  penyebab sesuai fitur yang belum diimplementasikan.
- Green terfokus: 10/10 test Create/authorization lulus.
- Regresi app: seluruh 27/27 test Announcements lulus.
- Smoke test superuser berhasil: tombol Add muncul, form dapat disubmit, redirect ke
  detail berhasil, tanggal pembuatan tampil, dan creator tersimpan sebagai akun
  superuser yang sedang login.
- Tidak ada migration baru pada Checkpoint 3.
- Coverage belum diukur dan tidak ada angka coverage yang diklaim.

## Kontribusi AI

### 2026-10-27 - Checkpoint 1: Model Announcement

- **Tool:** OpenAI Codex.
- **Tujuan:** audit referensi PBP, merancang model, menulis unit test dengan alur TDD,
  mereview migration, menjelaskan kode, dan menyiapkan dokumentasi.
- **Instruksi penting:** hanya mengerjakan Checkpoint 1; migration, testing, dan Git
  dijalankan oleh developer; tidak mengubah modul anggota lain; tidak mengimplementasikan
  UI atau interaktivitas.
- **File yang dibuat/diubah:** `models.py`, `tests.py`, `migrations/0001_initial.py`, dan
  `announcement.md` dalam app Announcements.
- **Saran/implementasi AI:** schema UUID, relasi creator dengan `SET_NULL`, timestamps,
  ordering, index tanggal, tujuh unit test model, serta dokumentasi ini.
- **Kontribusi manual developer:** menyetujui rancangan, menjalankan Red test,
  `makemigrations`, `migrate`, kedua percobaan Green test, dan commit fase Red.
- **Koreksi manual developer:** belum ada koreksi kode yang dilaporkan.
- **Limitasi/kesalahan AI:** test awal yang menghapus User tidak terisolasi dari relasi
  Weekly Challenge dan memicu error tabel yang tidak tersedia. Test kemudian dipersempit
  tanpa mengubah modul tersebut.
- **Hasil pengujian:** 7/7 model test lulus; coverage belum diukur.
- **Commit terkait:** `ed1f941 test(announcements): definisikan perilaku model announcement`
  dan `1cd337c feat(announcements): tambahkan model announcement`.

### 2026-10-27 - Checkpoint 2: Public Read dan Database Filtering

- **Tool:** OpenAI Codex.
- **Tujuan:** merancang kontrak test, mengimplementasikan public Read, ORM search/sort,
  endpoint JSON, URL routing, dan server-rendered responsive baseline.
- **Instruksi penting:** tidak mengimplementasikan CRUD, permission controls, Fetch,
  HTMX, Firebase, atau tombol frontpage; perubahan global URL telah disetujui developer.
- **File yang dibuat/diubah:** `announcements/tests.py`, `announcements/views.py`,
  `announcements/urls.py`, `templates/announcements/list.html`, `minlife/urls.py`,
  `minlife/urls_api.py`, dan dokumentasi ini.
- **Saran/implementasi AI:** helper QuerySet bersama, allowlist sort, search dengan `Q`,
  serializer tanggal timezone-aware, public HTML/JSON views, dan responsive list/detail.
- **Kontribusi manual developer:** memberi izin perubahan URL global, menjalankan Red,
  test Green terfokus, seluruh regression test Announcements, smoke test server, dan
  commit implementasi Green.
- **Koreksi manual developer:** belum ada koreksi kode yang dilaporkan.
- **Limitasi/kesalahan AI:** belum ada kesalahan implementasi Checkpoint 2 yang ditemukan;
  tampilan dengan dataset development yang terisi belum didokumentasikan.
- **Hasil pengujian:** 10/10 Read test dan 17/17 seluruh test Announcements lulus;
  coverage belum diukur.
- **Commit terkait:** `fedc36f test(announcements): definisikan perilaku baca dan
  penyaringan pengumuman` dan `680a06d feat(announcements): tambahkan baca publik dan
  filter database`.

### 2026-10-27 - Checkpoint 3: Authorization dan Create

- **Tool:** OpenAI Codex.
- **Tujuan:** merancang test role-based access, membuat `ModelForm`, melindungi Create
  pada server, mencegah creator spoofing, dan menambahkan UI Create baseline.
- **Instruksi penting:** hanya Create; tidak mengimplementasikan Update/Delete, modal,
  Fetch, HTMX, Firebase, atau perubahan navbar/frontpage.
- **File yang dibuat/diubah:** `announcements/tests.py`, `announcements/forms.py`,
  `announcements/views.py`, `announcements/urls.py`,
  `templates/announcements/list.html`, `templates/announcements/form.html`, dan
  dokumentasi ini.
- **Saran/implementasi AI:** `login_required`, `permission_required` dengan respons 403,
  `AnnouncementForm`, assignment creator dari request, CSRF form, dan conditional Add
  button.
- **Kontribusi manual developer:** menjalankan Red, test Green terfokus, seluruh
  regression test Announcements, membuat/menggunakan superuser development untuk smoke
  test, memverifikasi creator melalui Django shell, dan melakukan commit Green.
- **Koreksi manual developer:** meminta disclosure tool disederhanakan menjadi
  `OpenAI Codex`.
- **Limitasi/kesalahan AI:** belum ada kesalahan implementasi Checkpoint 3 yang ditemukan;
  modal dan asynchronous submit memang belum termasuk scope.
- **Hasil pengujian:** 10/10 Create test dan 27/27 seluruh test Announcements lulus;
  smoke test superuser berhasil; coverage belum diukur.
- **Commit terkait:** `7cacccf test(announcements): definisikan otorisasi dan pembuatan
  pengumuman` dan `9f68eb6 feat(announcements): tambahkan pembuatan pengumuman berizin`.

## Riwayat Checkpoint dan Conventional Commit

| Checkpoint | Status | Commit |
| --- | --- | --- |
| Red - unit test model | Selesai | `ed1f941 test(announcements): definisikan perilaku model announcement` |
| Green - model dan migration | Selesai | `1cd337c feat(announcements): tambahkan model announcement` |
| Dokumentasi Checkpoint 1 | Selesai | commit dokumentasi ini |
| Red Checkpoint 2 - Read/filter | Selesai | `fedc36f test(announcements): definisikan perilaku baca dan penyaringan pengumuman` |
| Green Checkpoint 2 - Read/filter | Selesai | `680a06d feat(announcements): tambahkan baca publik dan filter database` |
| Dokumentasi Checkpoint 2 | Selesai | commit dokumentasi ini |
| Red Checkpoint 3 - Authorization/Create | Selesai | `7cacccf test(announcements): definisikan otorisasi dan pembuatan pengumuman` |
| Green Checkpoint 3 - Authorization/Create | Selesai | `9f68eb6 feat(announcements): tambahkan pembuatan pengumuman berizin` |
| Dokumentasi Checkpoint 3 | Selesai | commit dokumentasi ini |

# Announcements

## Tujuan Modul

Modul Announcements menyediakan pengumuman resmi komunitas Minlife. Pengumuman dapat
dibaca oleh pengguna umum, sedangkan operasi create, update, dan delete akan dibatasi
untuk pengguna yang mempunyai Django model permissions yang sesuai.

Checkpoint 1 mencakup model data, migration awal, dan unit test model. Checkpoint 2
menambahkan public Read berupa list/detail HTML, endpoint JSON, database search, dan
sorting. Checkpoint 3 menambahkan Create server-rendered dengan `ModelForm` dan
authorization berbasis Django permission. Checkpoint 4 melengkapi Update/Delete dengan
permission server-side dan halaman konfirmasi. Interaktivitas tanpa reload, integrasi
Checkpoint 5A menambahkan Read, search, sorting, serta expand/collapse dinamis dengan
HTMX. Checkpoint 5B menambahkan modal Create, Edit, dan Delete berbasis HTMX dengan
halaman terpisah sebagai fallback. Checkpoint 6A menambahkan penyimpanan Firebase
Installation ID dan endpoint subscribe/unsubscribe. Integrasi frontpage, Web SDK,
service worker, serta pengiriman Firebase Cloud Messaging belum diimplementasikan.

## Arsitektur Django MVT

- **Model:** `Announcement` sudah diimplementasikan pada `models.py`.
- **View:** list/detail HTML penuh atau fragment HTMX, list/detail JSON, Create, Update,
  dan Delete sudah diimplementasikan.
- **Template:** `templates/announcements/list.html` menyediakan kerangka halaman,
  sedangkan `templates/announcements/_results.html` menyediakan fragment hasil yang
  responsif dan mengikuti pola list/detail Figma.
- **URL:** HTML tersedia di `/announcements/`; endpoint data tersedia di
  `/api/announcements` dan `/api/announcement/<uuid>`.
- **Form:** `AnnouncementForm` dipakai ulang oleh Create dan Update serta hanya
  mengekspos title dan content.
- **Subscription:** endpoint login-only di bawah `/announcements/notifications/`
  menyimpan atau menghapus Installation ID tanpa memanggil Firebase dari server.

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

Model `FCMSubscription` ditambahkan melalui migration `0002_fcmsubscription`. Satu user
dapat mempunyai beberapa instalasi browser melalui relasi `fcm_subscriptions`, sedangkan
`installation_id` bersifat unik agar satu browser hanya terkait dengan satu user aktif.
Model memakai UUID, `created_at`, `updated_at`, dan `CASCADE` ketika user dihapus.

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

Seluruh view yang mengubah data memeriksa permission pada server. Menyembunyikan tombol
di template hanya menjadi perlindungan UX, bukan pengganti authorization server-side.

Create view sudah mengikuti aturan tersebut. Tombol Add hanya dirender ketika
`request.user.has_perm("announcements.add_announcement")` bernilai benar, dan endpoint
tetap melakukan pemeriksaan permission secara independen. `created_by` selalu ditetapkan
dari `request.user`; nilai creator yang dikirim melalui POST diabaikan.

Update memerlukan `announcements.change_announcement`, sedangkan Delete memerlukan
`announcements.delete_announcement`. Edit memakai form tanpa field creator/timestamp,
sehingga `created_by` dan `created_at` tetap, sementara `updated_at` diperbarui ketika
form disimpan. GET Delete hanya menampilkan konfirmasi; penghapusan dilakukan melalui
POST yang dilindungi CSRF.

Subscribe dan unsubscribe FCM memerlukan user login serta hanya menerima POST JSON.
Subscribe memakai user dari session, bukan payload. Installation ID yang sama dapat
dipindahkan ke user yang sedang login agar browser bersama tidak tetap terhubung ke akun
lama. Unsubscribe hanya menghapus subscription milik user aktif dan bersifat idempotent;
user tidak dapat menghapus Installation ID milik user lain.

## Interaktivitas

Checkpoint 5A menggunakan HTMX 2.0.8 untuk Read dinamis. Fetch API sempat dibuat sebagai
prototipe, tetapi diganti sebelum commit fitur karena HTMX lebih sesuai dengan rendering
server Django MVT, lebih ringkas untuk didemokan, dan tidak memerlukan state serta
manipulasi DOM manual. Endpoint JSON tetap dipertahankan sebagai API, tetapi UI HTMX
mengambil HTML fragment agar respons dapat langsung ditukar ke DOM.

Search mengirim GET setelah debounce 300 ms dan sorting mengirim GET ketika pilihan
berubah. Klik card dan `Show less` juga menggunakan GET HTMX. Semua operasi menargetkan
`#announcement-results`, memakai `outerHTML`, dan memperbarui URL melalui
`hx-push-url`, sehingga Back/Forward browser tetap didukung. View memeriksa header
`HX-Request`: request biasa mendapat halaman penuh, sedangkan request HTMX hanya mendapat
`_results.html`.

Link `href`, form GET, ORM filtering, dan server-rendered HTML tetap menjadi baseline.
Tidak ada JavaScript custom Announcements pada Checkpoint 5A; atribut `hx-*` dijalankan
oleh library HTMX. Create, Update, dan Delete masih memakai form Django, redirect, serta
shared toast kelompok.

Checkpoint 5B menambahkan progressive enhancement untuk mutation. Request biasa tetap
merender `form.html` atau `confirm_delete.html`, sedangkan request HTMX merender partial
`_form.html` atau `_confirm_delete.html` ke native `<dialog>`. Submit valid mengembalikan
fragment `_results.html` dengan `HX-Retarget`, `HX-Reswap`, dan `HX-Trigger`; submit tidak
valid merender ulang error form di dalam dialog. Search dan sort dibawa melalui form agar
state filter tetap konsisten setelah mutation.

`static/announcements/js/dialog.js` hanya menjadi glue untuk membuka/menutup native
dialog dan meneruskan event sukses HTMX ke shared `toast.fire()`. Request, validasi,
authorization, dan DOM swap tetap ditangani HTMX serta Django. Full-page CRUD tetap
tersedia melalui URL yang sama ketika HTMX tidak tersedia atau URL dibuka langsung.

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

## Testing Checkpoint 4

Test Update/Delete dan authorization mencakup:

- Guest diarahkan ke login untuk Update/Delete.
- User biasa menerima 403 dan tidak dapat mengubah atau menghapus data.
- Moderator dan superuser dapat Update/Delete.
- Edit mempertahankan `created_by` dan `created_at`, serta memperbarui `updated_at`.
- Invalid Edit dirender ulang tanpa menyimpan perubahan.
- GET Delete hanya menampilkan konfirmasi dan tidak menghapus data.
- Penghapusan berhasil melalui POST.
- Tombol Edit/Delete hanya muncul untuk user berwenang.
- Missing UUID menghasilkan 404 dan method tidak didukung menghasilkan 405.

Hasil aktual:

- Fase Red: 11/11 test error karena route Update/Delete belum tersedia; penyebab sesuai
  fitur yang belum diimplementasikan.
- Green terfokus: 11/11 test Update/Delete lulus.
- Regresi final: seluruh 38/38 test Announcements lulus dalam 50.749 detik setelah
  perbaikan visual tombol `Show less`.
- Smoke test superuser untuk Edit, confirmation/Cancel Delete, dan POST Delete dinyatakan
  sesuai oleh developer.
- Tombol `Show less` diperjelas memakai shared outline button dan ikon chevron-up.
- Tidak ada migration baru pada Checkpoint 4.
- Coverage belum diukur dan tidak ada angka coverage yang diklaim.

## Testing Checkpoint 5A

Test HTMX Read mencakup:

- Library HTMX dan atribut filter dinamis tersedia pada halaman list.
- Search memakai debounce 300 ms.
- Request dengan header `HX-Request` hanya merender `_results.html`.
- Link detail mempunyai navigasi normal sebagai fallback sekaligus atribut HTMX.
- Detail HTMX menampilkan announcement yang dipilih.

Hasil aktual:

- Kontrak test awal Checkpoint 5A menggunakan Fetch API, kemudian disesuaikan ke HTMX
  sebelum implementasi fitur di-commit.
- Green pertama: 2/3 test lulus; satu assertion gagal karena separator query pada HTML
  memakai `&` alih-alih `&amp;`.
- Markup query diperbaiki menjadi HTML valid dan Green kedua menghasilkan 3/3 test HTMX
  lulus dalam 1.029 detik.
- Regresi final: seluruh 41/41 test Announcements lulus dalam 41.890 detik.
- Smoke test browser dinyatakan aman oleh developer: search/sort bekerja otomatis,
  detail expand/collapse tanpa full reload, tampilan responsif sesuai, dan request HTMX
  terverifikasi bertipe XHR.
- Tombol Apply dihapus karena search dan sort sudah otomatis.
- Warning penggunaan Tailwind CDN berasal dari shared `base.html`, tidak menyebabkan
  kegagalan, dan tidak diubah sepihak dalam modul Announcements.
- Coverage belum diukur dan tidak ada angka coverage yang diklaim.

## Testing Checkpoint 5B

Test mutation HTMX mencakup:

- Kontrol moderator menargetkan native dialog HTMX.
- GET HTMX Create dan Update hanya mengembalikan fragment form.
- Invalid Create menampilkan error di dialog tanpa membuat data.
- Valid Create memperbarui results, menyimpan creator dari user aktif, dan mengirim
  event sukses.
- Valid Update mempertahankan creator dan `created_at`, memperbarui results, dan
  mengirim event sukses.
- GET Delete hanya mengembalikan fragment konfirmasi; POST Delete menghapus data,
  memperbarui results, dan mengirim event sukses.
- Success response menetapkan `HX-Retarget`, `HX-Reswap`, dan `HX-Trigger` yang sesuai.

Hasil aktual:

- Fase Red: 7 test gagal karena dialog, partial form/confirmation, dan response mutation
  HTMX belum tersedia; penyebab sesuai fitur yang belum diimplementasikan.
- Green terfokus: seluruh 7/7 test mutation HTMX lulus.
- Regresi final sebelum commit: seluruh 48/48 test Announcements lulus.
- Smoke test browser dinyatakan selesai oleh developer. Add modal, detail expansion,
  centering dialog, dan wrapping konten panjang diperiksa secara visual selama smoke
  test; behavior mutation lainnya dicakup oleh automated test.
- Modal sempat berada di kiri karena shared CSS mereset margin semua elemen; diperbaiki
  dengan centering eksplisit, batas tinggi viewport, dan overflow scroll.
- Detail desktop sempat terlalu lebar dan ter-stretch setinggi list; diperbaiki menjadi
  dua kolom seimbang dengan content-height.
- Teks panjang tanpa spasi sempat keluar dari card; diperbaiki dengan `min-w-0` dan
  wrapping kata pada title/content desktop maupun mobile.
- Coverage belum diukur dan tidak ada angka coverage yang diklaim.

## Testing Checkpoint 6A

Test subscription FCM mencakup:

- UUID, field unik Installation ID, relasi User, dan ordering model.
- Guest diarahkan ke login untuk subscribe/unsubscribe.
- User login dapat mendaftarkan Installation ID.
- Installation ID yang sudah ada dipindahkan ke user yang sedang login tanpa duplikasi.
- JSON rusak, ID kosong, tipe non-string, dan ID terlalu panjang ditolak dengan 400.
- User dapat unsubscribe secara idempotent.
- User tidak dapat menghapus subscription milik user lain.
- Endpoint hanya menerima POST.

Hasil aktual:

- Fase Red: 8 test menghasilkan error karena model dan route subscription belum tersedia.
  Lima subtest invalid payload menyebabkan jumlah error pada output lebih besar dari
  jumlah test, sesuai kontrak yang belum diimplementasikan.
- Migration `announcements.0002_fcmsubscription` dibuat dan diterapkan manual oleh
  developer.
- Green terfokus: seluruh 8/8 test subscription lulus dalam 2.715 detik.
- Regresi app: seluruh 56/56 test Announcements lulus sebelum commit Green.
- Full suite kelompok memiliki satu kegagalan eksternal pada `users.tests` karena test
  membandingkan bound method `get_zen_points` dengan integer tanpa memanggil method;
  203 test lain lulus dan masalah telah dilaporkan kepada pemilik modul.
- Belum ada dependency `firebase-admin`, panggilan jaringan, Web SDK, service worker,
  atau pengiriman push nyata pada Checkpoint 6A.
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

### 2026-10-27 - Checkpoint 4: Authorization Update dan Delete

- **Tool:** OpenAI Codex.
- **Tujuan:** merancang test Update/Delete, memakai ulang ModelForm, menjaga metadata,
  melindungi endpoint berdasarkan permission, dan membuat konfirmasi penghapusan.
- **Instruksi penting:** belum mengimplementasikan modal, Fetch, HTMX, Firebase, atau
  perubahan navbar/frontpage.
- **File yang dibuat/diubah:** `announcements/tests.py`, `announcements/views.py`,
  `announcements/urls.py`, `templates/announcements/form.html`,
  `templates/announcements/list.html`, `templates/announcements/confirm_delete.html`, dan
  dokumentasi ini.
- **Saran/implementasi AI:** permission server-side, form Update dengan instance,
  POST-only deletion setelah GET confirmation, role-based controls, serta outline button
  untuk `Show less`.
- **Kontribusi manual developer:** menjalankan Red, test Green terfokus, dua regression
  test seluruh app, smoke test Update/Delete, meminta `Show less` dibuat lebih jelas,
  dan melakukan commit Green.
- **Koreksi manual developer:** meminta tombol `Show less` dibedakan dari isi announcement;
  styling kemudian memakai shared outline button dan ikon chevron-up.
- **Limitasi/kesalahan AI:** patch awal ditolak sebelum diterapkan karena menargetkan
  `views.py` dua kali dalam satu patch; patch kemudian digabung dan berhasil tanpa
  perubahan parsial. Modal dan asynchronous CRUD belum termasuk scope.
- **Hasil pengujian:** 11/11 Update/Delete test dan 38/38 seluruh test Announcements
  lulus; smoke test superuser berhasil; coverage belum diukur.
- **Commit terkait:** `d6476e7 test(announcements): definisikan otorisasi ubah dan hapus
  pengumuman` dan `4cccc40 feat(announcements): tambahkan ubah dan hapus pengumuman
  berizin`.

### 2026-10-28 - Checkpoint 5A: Read Dinamis dengan HTMX

- **Tool:** OpenAI Codex.
- **Tujuan:** menambahkan search, sorting, dan expand/collapse tanpa full-page reload
  dengan tetap mempertahankan server-rendered fallback dan Django ORM filtering.
- **Instruksi penting:** membandingkan Fetch API dan HTMX, memilih pendekatan yang mudah
  dipahami saat demo, mempertahankan endpoint JSON, serta tidak mengimplementasikan
  asynchronous mutation atau Firebase pada tahap ini.
- **File yang dibuat/diubah:** `announcements/tests.py`, `announcements/views.py`,
  `templates/announcements/list.html`, `templates/announcements/_results.html`, dan
  dokumentasi ini.
- **Saran/implementasi AI:** deteksi header `HX-Request`, fragment template reusable,
  debounce 300 ms, partial swap, URL history, loading indicator, dan fallback link/form.
- **Kontribusi manual developer:** memilih HTMX setelah membandingkan kompleksitas demo,
  menjalankan Red/Green serta regression test, melakukan smoke test browser dan Network,
  menyetujui penghapusan tombol Apply, dan melakukan commit test/fitur.
- **Koreksi manual developer:** meminta prototipe Fetch diganti dengan HTMX karena kode
  lebih mudah dipahami dan dijelaskan saat demo.
- **Limitasi/kesalahan AI:** kontrak awal memakai Fetch API sebelum keputusan direvisi;
  assertion HTML pertama juga menemukan separator query yang belum memakai `&amp;`.
  Keduanya dikoreksi sebelum commit fitur HTMX.
- **Hasil pengujian:** 3/3 HTMX test dan 41/41 seluruh test Announcements lulus; smoke
  test browser berhasil; coverage belum diukur.
- **Commit terkait:** `9afec6d test(announcements): menyesuaikan kontrak baca dinamis ke
  htmx` dan `c0cf75d feat(announcements): tambahkan baca dinamis dengan htmx`.

### 2026-10-29 - Checkpoint 5B: Modal CRUD Dinamis dengan HTMX

- **Tool:** OpenAI Codex.
- **Tujuan:** meningkatkan Create/Edit/Delete menjadi mutation HTMX dalam modal tanpa
  menghapus halaman server-rendered dan authorization yang sudah ada.
- **Instruksi penting:** mempertahankan fallback direct URL, memakai komponen kelompok,
  menjaga kode mudah didemokan, tidak mengubah shared toast, dan belum mengerjakan
  Firebase atau integrasi frontpage.
- **File yang dibuat/diubah:** `announcements/tests.py`, `announcements/views.py`,
  seluruh template Announcements yang berkaitan dengan CRUD/results,
  `static/announcements/js/dialog.js`, dan dokumentasi ini.
- **Saran/implementasi AI:** partial form/confirmation reusable, native dialog,
  `HX-Retarget`, `HX-Reswap`, `HX-Trigger`, filter preservation, serta JavaScript kecil
  untuk dialog dan pemanggilan shared toast.
- **Kontribusi manual developer:** menyetujui pola modal dengan full-page fallback,
  menjalankan Red/Green dan regression test, melakukan smoke test, menemukan masalah
  centering modal, ukuran detail, dan overflow teks, serta melakukan commit test/fitur.
- **Koreksi manual developer:** meminta penjelasan ulang fallback dan kebutuhan
  JavaScript, lalu melaporkan tiga masalah visual saat smoke test untuk diperbaiki.
- **Limitasi/kesalahan AI:** styling awal mengandalkan centering bawaan `<dialog>` yang
  tertimpa reset margin shared; grid detail awal juga terlalu besar dan belum menangani
  kata tanpa spasi. Seluruh masalah diperbaiki sebelum commit fitur.
- **Hasil pengujian:** 7/7 mutation HTMX test dan 48/48 seluruh test Announcements
  lulus; smoke test browser selesai; coverage belum diukur.
- **Commit terkait:** `a423850 test(announcements): definisikan mutasi dinamis dengan
  htmx` dan `0e7902c feat(announcements): tambahkan modal crud dinamis dengan htmx`.

### 2026-10-29 - Checkpoint 6A: Subscription FCM

- **Tool:** OpenAI Codex.
- **Tujuan:** menyediakan penyimpanan Firebase Installation ID dan endpoint aman untuk
  opt-in/opt-out sebelum mengintegrasikan Firebase Web SDK atau pengiriman push.
- **Instruksi penting:** memakai API FID terbaru, tidak melakukan request Firebase nyata,
  tidak menginstal dependency sebelum dibutuhkan, dan tidak mengubah modul teman yang
  mempunyai kegagalan test eksternal.
- **File yang dibuat/diubah:** `announcements/tests.py`, `announcements/models.py`,
  `announcements/views.py`, `announcements/urls.py`, migration
  `0002_fcmsubscription.py`, dan dokumentasi ini.
- **Saran/implementasi AI:** model UUID dengan Installation ID unik, relasi multi-browser
  ke User, endpoint JSON login-only, validasi payload, reassignment browser ke akun aktif,
  serta unsubscribe idempotent dan terisolasi per user.
- **Kontribusi manual developer:** menyiapkan Firebase project/config/VAPID/service
  account lokal, menyinkronkan `dev`, menjalankan migration dan Red/Green test, serta
  melakukan commit test dan fitur.
- **Koreksi manual developer:** meminta klarifikasi virtual environment, konfigurasi
  lokal vs PWS, Firebase API, dan service-account credential sebelum implementasi.
- **Limitasi/kesalahan AI:** full test suite tidak seluruhnya hijau karena satu test
  modul `users` memanggil method secara tidak tepat; AI hanya mendiagnosis dan tidak
  mengubah modul milik anggota lain.
- **Hasil pengujian:** 8/8 subscription test dan 56/56 seluruh test Announcements lulus;
  full suite kelompok 203 lulus dan 1 gagal pada modul `users`; coverage belum diukur.
- **Commit terkait:** `35acfdd test(announcements): definisikan langganan notifikasi fcm`
  dan `e87436f feat(announcements): tambahkan langganan notifikasi fcm`.

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
| Red Checkpoint 4 - Authorization Update/Delete | Selesai | `d6476e7 test(announcements): definisikan otorisasi ubah dan hapus pengumuman` |
| Green Checkpoint 4 - Authorization Update/Delete | Selesai | `4cccc40 feat(announcements): tambahkan ubah dan hapus pengumuman berizin` |
| Dokumentasi Checkpoint 4 | Selesai | commit dokumentasi ini |
| Red/revisi Checkpoint 5A - Read dinamis HTMX | Selesai | `9afec6d test(announcements): menyesuaikan kontrak baca dinamis ke htmx` |
| Green Checkpoint 5A - Read dinamis HTMX | Selesai | `c0cf75d feat(announcements): tambahkan baca dinamis dengan htmx` |
| Dokumentasi Checkpoint 5A | Selesai | commit dokumentasi ini |
| Red Checkpoint 5B - Mutation HTMX | Selesai | `a423850 test(announcements): definisikan mutasi dinamis dengan htmx` |
| Green Checkpoint 5B - Modal CRUD HTMX | Selesai | `0e7902c feat(announcements): tambahkan modal crud dinamis dengan htmx` |
| Dokumentasi Checkpoint 5B | Selesai | commit dokumentasi ini |
| Red Checkpoint 6A - Subscription FCM | Selesai | `35acfdd test(announcements): definisikan langganan notifikasi fcm` |
| Green Checkpoint 6A - Subscription FCM | Selesai | `e87436f feat(announcements): tambahkan langganan notifikasi fcm` |
| Dokumentasi Checkpoint 6A | Selesai | commit dokumentasi ini |

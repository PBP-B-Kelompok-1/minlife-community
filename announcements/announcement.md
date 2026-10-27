# Announcements

## Tujuan Modul

Modul Announcements menyediakan pengumuman resmi komunitas Minlife. Pengumuman dapat
dibaca oleh pengguna umum, sedangkan operasi create, update, dan delete akan dibatasi
untuk pengguna yang mempunyai Django model permissions yang sesuai.

Checkpoint 1 hanya mencakup model data, migration awal, dan unit test model. Listing,
detail, forms, views, URLs, templates, interaktivitas, integrasi frontpage, dan Firebase
Cloud Messaging belum diimplementasikan.

## Arsitektur Django MVT

- **Model:** `Announcement` sudah diimplementasikan pada `models.py`.
- **View:** pending untuk checkpoint Read/CRUD.
- **Template:** pending; nantinya mengikuti Figma dan shared components kelompok.
- **URL:** pending.
- **Form:** pending; Create/Edit direncanakan menggunakan `ModelForm`.

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

## Authentication dan Authorization

Authorization CRUD belum diimplementasikan pada Checkpoint 1. Rencana berikutnya
adalah menggunakan permissions Django yang sudah diberikan kepada group `Moderator`:

- `announcements.add_announcement`
- `announcements.change_announcement`
- `announcements.delete_announcement`

View nantinya wajib memeriksa permission pada server. Menyembunyikan tombol di template
hanya akan menjadi perlindungan UX, bukan pengganti authorization server-side.

## Interaktivitas

Keputusan Fetch API, HTMX, atau hybrid berstatus **pending**. Tidak ada AJAX, HTMX, atau
kode UI yang ditambahkan pada Checkpoint 1.

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

## Keputusan Teknis Checkpoint 1

- Menggunakan `settings.AUTH_USER_MODEL` agar relasi mengikuti custom User project dan
  migration memakai swappable dependency.
- Menggunakan UUID agar konsisten dengan model utama lain di repository.
- Menggunakan `SET_NULL` untuk mempertahankan pengumuman ketika creator tidak tersedia.
- Tidak menambahkan constraint, dependency, atau abstraction yang belum diperlukan.
- Tidak mengubah modul anggota lain untuk memperbaiki masalah migration Weekly Challenge.
- Tidak melakukan refactor tambahan karena implementasi model sudah minimum dan jelas.

## Kontribusi AI

### 2026-10-27 - Checkpoint 1: Model Announcement

- **Tool:** OpenAI Codex; model exact belum diverifikasi.
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

## Riwayat Checkpoint dan Conventional Commit

| Checkpoint | Status | Commit |
| --- | --- | --- |
| Red - unit test model | Selesai | `ed1f941 test(announcements): definisikan perilaku model announcement` |
| Green - model dan migration | Selesai | `1cd337c feat(announcements): tambahkan model announcement` |
| Dokumentasi Checkpoint 1 | Selesai | commit dokumentasi ini |
| Checkpoint 2 - Read/filter | Belum dimulai | pending |

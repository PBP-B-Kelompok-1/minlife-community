# Weekly Challenge

Dokumen koordinasi modul Weekly Challenge. Pemilik modul: Clement Kevin Tanadi (2506632892).

## Ringkasan

Moderator membuat challenge mingguan yang berisi latar belakang, deskripsi,
tujuan, tanggal mulai, dan maksimal tujuh tugas harian. Setiap challenge
memiliki satu badge. Submission menggunakan tag bersama `Weekly Challenge`.

Pengguna mengikuti challenge aktif melalui formulir Post biasa dengan mengisi foto
bukti. Post yang diberi tag `Weekly Challenge` tercatat sebagai
`ChallengeSubmission` untuk challenge yang sedang aktif. Setelah skor Post
mencapai ambang `upvote_threshold`, penulis mendapat badge challenge tersebut.

Weekly Challenge menggunakan model dari aplikasi Posts dan Users. Posts mengimpor helper yang diperlukan dari `weeklychallenge/services.py`; Users tidak perlu mengimpor kode dari Weekly Challenge.

## Alur challenge

1. Moderator membuat challenge. Dalam satu transaksi, sistem membuat challenge,
   badge, dan tugas-tugasnya.
2. Pengguna hanya dapat mengikuti challenge yang sedang aktif. Mereka membuat
   Post melalui formulir Posts, menggunakan tag `Weekly Challenge`, dan mengunggah
   `challenge_image`.
4. Setelah Post disimpan dengan tag challenge, sinyal `post_save` membuat `ChallengeSubmission`. Satu pengguna hanya dapat memiliki satu submission per challenge.
5. Sinyal pada perubahan Vote mengevaluasi skor Post, yaitu upvote dikurangi downvote. Jika skor memenuhi ambang challenge, sistem memberikan badge kepada penulis.
6. Badge yang sudah diberikan tidak dicabut jika skor turun atau Post dihapus.

Challenge tidak boleh memiliki rentang tanggal yang tumpang tindih. Dengan demikian, hanya ada satu challenge aktif pada satu waktu.

## Integrasi dengan Posts (Jovan)

- Sediakan field dan perilaku Post yang dibutuhkan Weekly Challenge: `author`, `title`, `content`, `tags`, `challenge_image`, dan `get_vote_count()`.
- Gunakan `get_current_challenge()` untuk menemukan challenge aktif, dan `user_has_submitted(user, challenge)` untuk memeriksa apakah pengguna sudah ikut.
- Tampilkan pilihan ikut challenge hanya saat ada challenge aktif. Nonaktifkan pilihan itu untuk pengguna yang sudah memiliki submission.
- Gunakan tag bersama `Weekly Challenge` untuk submission; jangan membuat tag per
  challenge.
- Setelah Post disimpan dengan tag `Weekly Challenge`, sinyal menghubungkan Post
  ke challenge yang sedang aktif. Jangan membuat `ChallengeSubmission` secara
  langsung atau menulis ke tabel perantara; sinyal mengurus pencatatannya.
- Setelah `form.save_m2m()` selesai, simpan Post sekali lagi agar `post_save` melihat tag challenge yang sudah terpasang dan membuat submission.
- Saat mengedit Post, pertahankan tag `Weekly Challenge` yang sudah terpasang
  ketika menyimpan ulang pilihan tag biasa. `form.save_m2m()` atau `tags.set()`
  dapat menghapus tag tersebut jika tidak disertakan.
- Wajibkan `challenge_image` saat pengguna memilih ikut challenge.
- Gunakan sinyal `post_save` dan `post_delete` pada Vote untuk mengevaluasi badge. Jangan mengubah Vote melalui `update()` atau `bulk_create()` karena cara tersebut tidak memicu sinyal model.
- Field `Challenge.tag` dipertahankan hanya untuk kompatibilitas data lama dan
  tidak digunakan untuk challenge baru.
- URL detail Post menggunakan UUID; tautan dari halaman challenge harus memakai nama URL milik Posts, bukan merangkai URL sendiri.
- Pastikan `MEDIA_ROOT` dan `MEDIA_URL` dikonfigurasi, serta berkas unggahan tetap tersedia setelah deployment ke PWS.
- Perbaiki `Vote.__str__` agar aman untuk Vote komentar, yang tidak memiliki Post.

## Integrasi dengan Users (Husainah)

- Sediakan model `Badge` dan `UserBadge`. Setiap `Challenge` memiliki tepat satu Badge, dan satu Badge hanya dapat dimiliki oleh satu Challenge. Satu pengguna tidak dapat menerima Badge yang sama lebih dari sekali.
- `UserBadge.badge` tetap menggunakan kebijakan penghapusan yang menjaga Badge
  dan riwayat UserBadge yang sudah diperoleh ketika Challenge dihapus.
- Badge dibuat oleh layanan Weekly Challenge saat moderator membuat challenge. `UserBadge` diberikan oleh layanan badge menggunakan `get_or_create`; jangan membuat keduanya dari alur lain.
- Pastikan `Badge.__str__` mengembalikan nama badge.
- Profil pengguna dapat menampilkan badge melalui `user.user_badges`, diurutkan menurut `earned_at`.
- Tampilkan tombol membuat challenge kepada user yang memiliki izin `weeklychallenge.add_challenge`; anggota Group `Moderator` biasanya menerima izin tersebut, dan superuser juga dapat mengaksesnya. Berikan izin `add_challenge`, `change_challenge`, dan `delete_challenge` untuk aplikasi `weeklychallenge` setelah migrasi membuat izin tersebut.
- Gunakan `from django.conf import settings` untuk mengakses `AUTH_USER_MODEL` dari model Users.

## Setup dan pemeriksaan bersama

- Pastikan `users`, `posts`, dan `weeklychallenge` terdaftar di `INSTALLED_APPS` dan migrasi yang diperlukan sudah diterapkan.
- Buat challenge melalui `create_challenge()`, bukan `Challenge.objects.create()` langsung, agar badge dan tag ikut dibuat secara konsisten.
- Sebelum menggabungkan perubahan, jalankan:

  ```powershell
  python manage.py check
  python manage.py test weeklychallenge posts
  ```

  Jalankan juga seluruh tes proyek sebelum menggabungkan perubahan lintas modul.

## Status implementasi

- [x] Model, relasi tag, dan migrasi.
- [x] Service untuk challenge aktif, pembuatan challenge, pemeriksaan submission, dan pemberian badge.
- [x] Form challenge dengan date picker, validasi rentang tanggal, validasi overlap, dan batas maksimal tujuh tugas.
- [x] View dan URL untuk halaman challenge, daftar/filter, detail, edit, hapus dengan konfirmasi, leaderboard, serta endpoint HTMX untuk form tugas.
- [x] Template responsif untuk desktop dan mobile menggunakan Tailwind dan HTMX.
- [x] HTMX untuk filter/search/pagination direktori, navigasi detail, leaderboard,
  form create/edit, task-row controls, dan konfirmasi delete.
- [x] Fallback non-HTMX untuk seluruh alur CRUD, termasuk form `action`, link
  `href`, request POST biasa, dan redirect HTTP standar.
- [x] Permission checks server-side, `HX-Redirect` untuk request anonim, CSRF
  header, error feedback, modal native `<dialog>`, dan event refresh
  `challengeChanged`.
- [x] Tes terfokus untuk service, form, model constraint, permission, filtering, rendering, update, delete, badge persistence, dan sinyal sudah tersedia.
- [x] Sinyal Django untuk submission berbasis tag dan pemberian badge berbasis Vote sudah diimplementasikan.

### Perilaku sinyal

Sinyal yang digunakan:

1. `post_save` pada `Post`.
   - Setelah Post tersimpan, cari tag challenge yang terpasang.
   - Submission hanya dibuat untuk challenge yang sedang aktif.
   - Buat `ChallengeSubmission` memakai author dan Post terkait melalui `get_or_create`.
   - Tangani `IntegrityError` agar submission duplikat tidak menggagalkan penyimpanan Post.
2. `post_save` dan `post_delete` pada `Vote`.
   - Abaikan Vote yang tidak memiliki `post_id`, seperti Vote pada komentar.
   - Evaluasi kelayakan badge dengan `award_badge_if_eligible(post)`.
   - Pada penghapusan Vote, abaikan kasus ketika Post terkait sudah tidak ada.
   - Badge yang sudah diperoleh tetap tersimpan dan tidak dicabut ketika skor turun.
3. Signal handlers didaftarkan melalui `WeeklychallengeConfig.ready()` dengan `dispatch_uid` agar tidak terhubung ganda.

## Keputusan yang disepakati

- Semua challenge memakai tag sistem bersama `Weekly Challenge`; pengguna tidak
  memilih tag per challenge.
- Submission dibuat hanya melalui formulir Post milik Posts, bukan melalui formulir atau view submission di Weekly Challenge.
- Challenge aktif menerima submission; challenge yang sudah lewat tidak.
- Maksimal tujuh tugas per challenge, bernomor 1 sampai 7, dan nomor hari tidak boleh duplikat dalam challenge yang sama.
- Satu pengguna hanya dapat mengirim satu submission untuk setiap challenge.
- Skor badge adalah upvote dikurangi downvote.
- Badge tidak dicabut setelah diberikan, termasuk jika skor turun atau Post dihapus.
- Perubahan Vote ditangani melalui sinyal model di Weekly Challenge.

## Keputusan implementasi

- Jika moderator menghapus challenge yang sudah memiliki submission, submission
  terkait terhapus, sedangkan Post, tag, Badge, dan UserBadge yang sudah
  diperoleh tetap ada. Badge yang sudah diperoleh tidak pernah dicabut.
- Badge challenge menggunakan relasi satu-ke-satu dan `SET_NULL` saat challenge
  dihapus. Badge tidak ikut terhapus karena tetap menjadi bukti pencapaian.
- Request HTMX tidak pernah menerima fragment untuk navigasi boosted atau history
  restore; kedua jenis request tersebut menerima halaman penuh agar reload dan
  tombol back tetap berfungsi.

## Validasi

Jalankan dari root project:

```powershell
python manage.py check
python manage.py test weeklychallenge posts
python manage.py makemigrations --check --dry-run
git diff --check
```

Test modul Weekly Challenge mencakup model, service, form, permission,
filtering, rendering, update, delete, persistence Badge, signal, dan interaksi
HTMX. Manual browser checks untuk responsive layout, keyboard focus, screen
reader, JS-disabled fallback, dan deployment tetap perlu dilakukan sebelum demo.

Pertanyaan terbuka yang tidak memblokir implementasi saat ini:

- Apakah nomor tugas perlu dibatasi oleh durasi challenge, selain batas tetap 1–7?

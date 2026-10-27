# Weekly Challenge

Dokumen koordinasi modul Weekly Challenge. Pemilik modul: Clement Kevin Tanadi (2506632892).

## Ringkasan

Moderator membuat challenge mingguan yang berisi latar belakang, deskripsi, tujuan, dan maksimal tujuh tugas harian. Setiap challenge memiliki satu badge dan satu tag khusus yang dibuat oleh sistem.

Pengguna mengikuti challenge aktif melalui formulir Post biasa dengan mengisi foto bukti. Post yang diberi tag khusus challenge tercatat sebagai `ChallengeSubmission`. Setelah skor Post mencapai ambang `upvote_threshold`, penulis mendapat badge challenge tersebut.

Weekly Challenge menggunakan model dari aplikasi Posts dan Users. Posts mengimpor helper yang diperlukan dari `weeklychallenge/services.py`; Users tidak perlu mengimpor kode dari Weekly Challenge.

## Alur challenge

1. Moderator membuat challenge. Dalam satu transaksi, sistem membuat challenge, badge, tag khusus, dan tugas-tugasnya.
2. Nama tag sistem menggunakan format `weeklychallenge<id-challenge>`. Relasinya disimpan di `Challenge.tag`.
3. Pengguna hanya dapat mengikuti challenge yang sedang aktif. Mereka membuat Post melalui formulir Posts, mencentang pilihan ikut challenge, dan mengunggah `challenge_image`.
4. Setelah tag challenge ditambahkan ke Post, sinyal `m2m_changed` membuat `ChallengeSubmission`. Satu pengguna hanya dapat memiliki satu submission per challenge.
5. Sinyal pada perubahan Vote mengevaluasi skor Post, yaitu upvote dikurangi downvote. Jika skor memenuhi ambang challenge, sistem memberikan badge kepada penulis.
6. Badge yang sudah diberikan tidak dicabut jika skor turun atau Post dihapus.

Challenge tidak boleh memiliki rentang tanggal yang tumpang tindih. Dengan demikian, hanya ada satu challenge aktif pada satu waktu.

## Integrasi dengan Posts (Jovan)

- Sediakan field dan perilaku Post yang dibutuhkan Weekly Challenge: `author`, `title`, `content`, `tags`, `challenge_image`, dan `get_vote_count()`.
- Gunakan `get_current_challenge()` untuk menemukan challenge aktif, dan `user_has_submitted(user, challenge)` untuk memeriksa apakah pengguna sudah ikut.
- Tampilkan pilihan ikut challenge hanya saat ada challenge aktif. Nonaktifkan pilihan itu untuk pengguna yang sudah memiliki submission.
- Tag khusus challenge tidak boleh muncul sebagai pilihan tag umum. Ambil tag umum dengan `Tag.objects.filter(challenge__isnull=True)`.
- Setelah Post disimpan, tambahkan tag challenge melalui `post.tags.add(challenge.tag)`. Jangan membuat `ChallengeSubmission` secara langsung atau menulis ke tabel perantara; sinyal mengurus pencatatannya.
- Saat mengedit Post, pertahankan tag challenge yang sudah terpasang ketika menyimpan ulang pilihan tag biasa. `form.save_m2m()` atau `tags.set()` dapat menghapus tag tersebut jika tidak disertakan.
- Wajibkan `challenge_image` saat pengguna memilih ikut challenge.
- Gunakan sinyal `post_save` dan `post_delete` pada Vote untuk mengevaluasi badge. Jangan mengubah Vote melalui `update()` atau `bulk_create()` karena cara tersebut tidak memicu sinyal model.
- Tangani `ProtectedError` jika penghapusan tag dicoba pada tag yang dipakai oleh challenge (`PROTECT`).
- URL detail Post menggunakan UUID; tautan dari halaman challenge harus memakai nama URL milik Posts, bukan merangkai URL sendiri.
- Pastikan `MEDIA_ROOT` dan `MEDIA_URL` dikonfigurasi, serta berkas unggahan tetap tersedia setelah deployment ke PWS.
- Perbaiki `Vote.__str__` agar aman untuk Vote komentar, yang tidak memiliki Post.

## Integrasi dengan Users (Husainah)

- Sediakan model `Badge` dan `UserBadge`. `Challenge.badge` merujuk ke Badge; satu pengguna tidak dapat menerima Badge yang sama lebih dari sekali.
- Badge dibuat oleh layanan Weekly Challenge saat moderator membuat challenge. `UserBadge` diberikan oleh layanan badge menggunakan `get_or_create`; jangan membuat keduanya dari alur lain.
- Pastikan `Badge.__str__` mengembalikan nama badge.
- Profil pengguna dapat menampilkan badge melalui `user.user_badges`, diurutkan menurut `earned_at`.
- Moderator menggunakan Django Group bernama `Moderator`, bukan pemeriksaan `is_staff`. Berikan izin `add_challenge`, `change_challenge`, dan `delete_challenge` untuk aplikasi `weeklychallenge` setelah migrasi membuat izin tersebut.
- Gunakan `from django.conf import settings` untuk mengakses `AUTH_USER_MODEL` dari model Users.

## Setup dan pemeriksaan bersama

- Pastikan `users`, `posts`, dan `weeklychallenge` terdaftar di `INSTALLED_APPS` dan migrasi yang diperlukan sudah diterapkan.
- Buat challenge melalui `create_challenge()`, bukan `Challenge.objects.create()` langsung, agar badge dan tag ikut dibuat secara konsisten.
- Sebelum menggabungkan perubahan, jalankan:

  ```powershell
  python manage.py check
  python manage.py test weeklychallenge
  ```

  Jalankan juga seluruh tes proyek sebelum menggabungkan perubahan lintas modul.

## Keputusan yang disepakati

- Setiap challenge memiliki satu tag sistem; pengguna tidak memilih tag tersebut dari daftar tag umum.
- Submission dibuat hanya melalui formulir Post milik Posts, bukan melalui formulir atau view submission di Weekly Challenge.
- Challenge aktif menerima submission; challenge yang sudah lewat tidak.
- Maksimal tujuh tugas per challenge, bernomor 1 sampai 7, dan nomor hari tidak boleh duplikat dalam challenge yang sama.
- Satu pengguna hanya dapat mengirim satu submission untuk setiap challenge.
- Skor badge adalah upvote dikurangi downvote.
- Badge tidak dicabut setelah diberikan, termasuk jika skor turun atau Post dihapus.
- Perubahan Vote ditangani melalui sinyal model di Weekly Challenge.

## Hal yang masih perlu diputuskan

- Apa yang seharusnya terjadi jika moderator menghapus challenge yang sudah memiliki submission? Perilaku saat ini: submission terkait terhapus, sedangkan Post dan tag tetap ada.
- Apakah nomor tugas perlu dibatasi oleh durasi challenge, selain batas tetap 1–7?

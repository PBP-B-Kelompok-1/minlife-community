# Weekly Challenge (Clement Kevin Tanadi - 2506632892)

Catatan koordinasi modul Weekly Challenge dengan modul lain. Kode ada di `weekly_challenge_models.py`.

## Cara kerja

Moderator membuat challenge. User mengirim submission berupa Post biasa yang diberi tag "Weekly Challenge" dan foto bukti. Setiap submission dicatat di `ChallengeSubmission` (satu user, satu submission per challenge). Saat skor Post mencapai `upvote_threshold`, user mendapat badge milik challenge tersebut.

Ketergantungan hanya satu arah: Weekly Challenge memakai Posts dan Users. Posts dan Users tidak perlu mengimpor apa pun dari Weekly Challenge.

## Yang dibutuhkan dari Posts (Jovan)

Field `Post` yang dipakai: `author`, `title`, `content`, `image`, `tags`, `upvote_count`, `downvote_count`. Tolong konfirmasi nama field-nya.

1. Setelah vote berubah, panggil `maybe_award_badge(post)` atau kirim signal yang bisa kami dengarkan.
2. Tag "Weekly Challenge" dibuat lewat migrasi data sejak awal.
3. Form post biasa menyembunyikan tag tersebut, supaya user tidak bisa memasangnya sendiri.
4. Skor yang dipakai: upvote dikurangi downvote. Beri tahu kalau skor sudah tersedia sebagai field atau method.

## Yang dibutuhkan dari Users (Husainah)

`Badge` dan `UserBadge` belum terdefinisi jelas. Usulan:

```python
class Badge(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon_url = models.URLField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

class UserBadge(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_badges")
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="awards")
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "badge"], name="unique_badge_per_user")]
```

- `Challenge.badge` menunjuk ke `Badge`. `Badge` tidak menyimpan `challengeId`, supaya tidak saling menunjuk.
- Saat moderator membuat challenge, `Badge` dibuat dalam satu transaksi yang sama.
- Role moderator memakai Group Django. Group `Moderator` perlu izin tambah, ubah, dan hapus untuk `Challenge`.

## Keputusan yang masih terbuka

- Vote untuk submission memakai model `Vote` milik Posts, atau sistem vote terpisah? Usulan: pakai `Vote` milik Posts, supaya lebih sederhana.
- Skor badge dihitung dari upvote saja atau upvote dikurangi downvote? Saat ini: upvote dikurangi downvote.
- Apakah challenge yang sudah lewat masih menerima submission? Saat ini: tidak.
- Apakah badge tetap ada kalau Post dihapus atau skornya turun? Saat ini: tetap ada.
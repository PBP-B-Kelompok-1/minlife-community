# PBP B Kelompok 1

## Deskripsi Aplikasi
**Community platform untuk mempromosikan lifestyle minimalist, suatu lifestyle yang mendukung sustainable living.**

Minimalist lifestyle adalah konsep hidup yang berfokus untuk menyederhanakan kepemilikan barang dan aktivitas sehari-hari agar hanya menyisakan hal-hal yang benar-benar esensial dan memberi nilai nyata. Ini berpusat seputar konsep memprioritaskan kualitas di atas kuantitas serta membuang segala bentuk kelebihan materi atau gangguan pikiran. Aplikasi kami bertujuan memberi insentif kepada para pengguna untuk mendalami lifestyle tersebut melalui kontak dengan komunitas yang luas. 

Bentuk aplikasi adalah _community platform_ yang berputar sekitar fitur posting yang fleksibel; setiap post dapat disusun dalam bentuk artikel, forum, atau bahkan listing barang yang ingin dijual/diberikan karena adanya fitur _tags_ sebagai alat kategorisasi. Aplikasi juga memiliki sistem-sistem interaktif seperti challenges. Secara personal, pengguna juga boleh membuat jurnal tentang perjalanan mengadopsi lifestyle minimalis. Tentu saja, ada moderasi pada platform ini; moderator dapat, misalnya, menghapus post dan membuat announcement.

Target pengguna adalah siapa saja yang berminat menghilangkan beban pikiran (declutter) dengan cara menempuh cara hidup yang baru.

## Anggota Kelompok
- Qisthan Albani Fasyah - 2506621434
- Enzo Susilo - 2506584382
- Jovan Finesta - 2506599144
- Husainah Syamsiah - 2506589036
- Clement Kevin Tanadi - 2506632892

---

## Tautan
#### PWS
https://clement-kevin-minlifecommunity.pws.cs.ui.ac.id 

#### Figma
https://www.figma.com/design/a7E8oOdT7QY1mf0E1UdtKS/Untitled?node-id=0-1&t=KeRtCcQylg4S9L7c-1 

---

## Daftar Modul

#### User (Husainah Syamsiah - 2506589036)
Setiap user akan disimpan di database dengan data seperti nama, link sosial media, dan poin yang terakumulasi. Fitur users dibutuhkan oleh modul-modul lainnya, seperti artikel dan weekly highlights.

Halaman profile akan memuat info-info publik user dan posting. Sebuah penanda tambahan muncul jika user tersebut adalah moderator.

#### Post (Jovan Finesta - 2506599144)
Posts menjadi halaman utama dari website ini.

Setiap pengguna dapat membuat post yang bebas diformat sebagai artikel, pertanyaan forum, maupun bentuk lainnya. Para pengguna dapat memberikan reply untuk memberikan tanggapan. Setiap post maupun reply dapat di-upvote maupun di-downvote. Upvote count diakumulasi di akun user.

Sebuah post juga dapat diberikan beberapa tag untuk mempermudah kategorisasi. Tag yang ada misalnya “question”, “article”, “poll”, dan “selling/giveaway”. Moderator dapat membuat tag kategori baru ketika diperlukan.

Setiap user dapat mengedit dan menghapus post atau komentar yang ia post. Moderator mempunyai permission menghapus semua post.

#### Announcement (Enzo Susilo - 2506584382)

Moderator dapat menambah announcement yang terdiri atas judul, isi, dan mungkin gambar yang bertopik tentang update terhadap aplikasi, rules, atau berita apa pun. 

Satu announcement terbaru akan muncul di atas halaman frontpage, dan terdapat tombol yang menampilkan semua announcement di page terpisah.

Modul ini akan terintegrasi dengan Firebase FCM untuk push notifications.

#### Personal goals (Qisthan Albani Fasyah - 2506621434)
Setiap user mendapatkan sebuah menu jurnal berisi kalender. Setiap tanggal pada kalender dapat ditekan untuk memunculkan modal berisi text editor untuk dituliskan status hari ini.

User dapat menuliskan goals, jurnal hari ini, atau apa pun yang cocok. User dapat membuat jurnal tersebut publik atau privat.

#### Weekly challenge (Clement Kevin Tanadi - 2506632892)
Setiap minggu, moderator akan membuat sebuah challenge untuk users ikuti. Pada setiap challenge, akan ada ‘latar belakang masalah’, ‘deskripsi challenge’, ‘tujuan/ekspektasi setelah challenge’. 

- Latar Belakang Masalah dapat berupa situasi yang tidak sesuai dengan cara pandang hidup minimalis. Contohnya, banyak barang yang berlebihan (misal kabel charger yang menjuntai di atas meja kerja sehingga mengganggu fokus saat bekerja).
- Deskripsi challenge merupakan deskripsi mengenai apa yang harus dilakukan user untuk dapat menyelesaikan challenge, contohnya “singkirkan barang yang tak bermanfaat di meja kerja kamu”.
- Tujuan/ekspektasi untuk menjelaskan impact apa yang dapat terjadi jika kita menyelesaikan challenge.

User dapat submit challenge dengan mengirim foto bukti dan penjelasan dengan text. Submission tersebut akan muncul di halaman challenge tersebut dan dapat di-approve oleh para user dengan cara memberi upvote. Sebuah badge yang terhubung pada challenge tersebut akan diberikan kepada user setelah mencapai sebuah threshold upvote.

## Public API yang dipakai

~~- **Firebase Authentication**: user accounts, login.~~ gunakan saja Auth Django

- **Firebase Cloud Messaging (FCM)** Push notifications

Notable libraries: `django-ckeditor` untuk textboxes, bootstrap?

## Peran user
User terbagi menjadi dua kategori:

#### User biasa
User dapat mendaftarkan akunnya dan berpartisipasi dalam komunitas melalui berbagai cara:

- Membuat post
- Memberikan komentar
- Memberikan upvote atau downvote untuk post atau komentar
- Melakukan submission weekly challenge

#### Moderator
Moderator adalah user yang dipercayai untuk mengatur komunitas, seperti menghapus post dan komentar yang ofensif dan membuat topik weekly challenge. Moderator dapat berpartisipasi dalam komunitas seperti user lain.

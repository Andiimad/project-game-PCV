# project-game-PCV
Game berbasis Python dan OpenCV yang terinspirasi dari mekanik *Magic Touch*. Pemain menggunakan objek berwarna tertentu di depan kamera untuk menyentuh empat titik pada layar sesuai urutan pola yang ditampilkan.

## Fitur

- Deteksi warna objek secara real-time menggunakan kamera.
- Pengaturan rentang warna melalui slider HSV.
- Empat titik interaktif yang posisinya bisa dipindahkan dengan mouse.
- Pola musuh seperti Zigzag, Segitiga, Huruf U, Kotak, Huruf N, dan Time Limit.
- Sistem skor, nyawa, wave, dan batas waktu.
- Tampilan mask untuk membantu kalibrasi deteksi warna.

## Persyaratan

- Python
- Webcam/kamera yang dapat diakses komputer
- Paket Python:
  - `opencv-python`
  - `numpy`



## Menjalankan Game

Simpan kode game sebagai `main.py`, lalu jalankan:

```bash
python projectgame.py
```
Game mencoba membuka kamera pada indeks `0`. Jika kamera tidak bisa dibuka, periksa izin kamera atau ubah `cv2.VideoCapture(0)` sesuai indeks kamera yang tersedia.

## Cara Bermain

1. Jalankan program dan pastikan kamera mengarah ke area bermain.
2. Atur empat titik pada jendela game dengan menyeret titik menggunakan mouse.
3. Gunakan objek berwarna yang sesuai dengan pengaturan deteksi kamera.
4. Tekan **Spasi** untuk memulai.
5. Ikuti pola musuh dengan menyentuh titik dalam urutan angka yang ditampilkan. Objek harus berada di area titik agar sentuhan terdeteksi.
6. Selesaikan pola sebelum waktu habis untuk mengalahkan musuh dan memperoleh skor.
7. Hindari menyentuh titik yang salah karena waktu akan berkurang. Jika waktu habis, nyawa berkurang.
8. Setelah **Game Over**, tekan **Spasi** untuk bermain kembali.

## Kontrol

| Kontrol | Fungsi |
|---|---|
| Seret titik dengan mouse | Memindahkan posisi titik |
| `Spasi` | Memulai permainan atau bermain kembali setelah Game Over |
| `r` | Mengembalikan titik ke posisi awal |
| `m` | Menampilkan atau menyembunyikan jendela Mask |
| `q` | Keluar dari game |

## Kalibrasi Deteksi Warna

Jendela **Controls** menyediakan slider berikut:

| Slider | Fungsi |
|---|---|
| `H center` | Memilih rona (*hue*) utama warna yang dideteksi |
| `H tol` | Mengatur toleransi rentang rona |
| `S min` | Batas minimum saturasi |
| `V min` | Batas minimum kecerahan |
| `Radius` | Mengubah ukuran area deteksi pada tiap titik |
| `Hit %` | Persentase minimum area titik yang harus tertutup warna terdeteksi |

Jendela **Mask** menampilkan hasil segmentasi: area putih adalah bagian gambar yang lolos filter warna, sedangkan area hitam tidak lolos. Gunakan tampilan ini untuk membantu menyesuaikan slider.

Nilai awal `H center` adalah `30`, yang kira-kira sesuai dengan warna kuning pada HSV OpenCV. Hasil deteksi dipengaruhi pencahayaan, kamera, dan warna objek. Sesuaikan slider sambil melihat jendela Mask.

## Konfigurasi Gameplay

Beberapa konstanta dapat diubah di bagian awal kode:

| Konstanta | Kegunaan |
|---|---|
| `NUM_POINTS` | Jumlah titik permainan |
| `START_LIVES` | Jumlah nyawa awal |
| `WRONG_PENALTY` | Pengurangan waktu ketika salah menyentuh titik |
| `KILLS_PER_WAVE` | Jumlah musuh yang dikalahkan untuk menaikkan wave |
| `DEBOUNCE` | Jeda untuk mencegah sentuhan yang sama terhitung berulang |
| `ON_FRAMES` | Jumlah frame berturut-turut yang diperlukan agar titik dianggap tersentuh |
| `SPRITE_SCALE` | Skala ukuran sprite musuh |
| `KEY_OUT_WHITE` | Mengaktifkan penghapusan warna putih pada sprite tanpa kanal alpha |

Batas waktu musuh dihitung berdasarkan wave. Pada awal permainan, batas waktu adalah 12 detik dan berkurang seiring kenaikan wave hingga minimum 5 detik.

## Sprite Musuh (Opsional)

Program mencari gambar pada folder proyek:

```text
project/
├── projectgame.py
└── enemies/
    ├── enemy1.png
```
`enemy.png` serta file PNG di folder `enemies/` akan dimuat jika tersedia. Jika tidak ada gambar yang valid, game tetap dapat berjalan tanpa sprite.

## Demo Gameplay

 [YouTube](https://youtu.be/PbfujhLL-MM).

## Struktur Proyek

```text
project/
├── projectgame.py
└── enemies/           # opsional
    ├── enemy_1.png
```

## Troubleshooting

- **Kamera tidak terbuka:** tutup aplikasi lain yang menggunakan kamera, periksa izin kamera, dan pastikan indeks kamera benar.
- **Objek tidak terdeteksi:** lihat jendela Mask, lalu atur `H center`, `H tol`, `S min`, dan `V min`.
- **Titik terlalu sulit atau mudah aktif:** sesuaikan `Hit %` dan `Radius`.
- **Banyak area lain ikut terdeteksi:** tingkatkan `S min` atau `V min`, atau perkecil `H tol`.
- **Sprite tidak muncul:** pastikan file berada di lokasi yang dicari program dan formatnya PNG/WebP.
- **Game tidak merespons:** periksa terminal untuk pesan error dan pastikan jendela OpenCV masih berjalan.

## Teknologi

- Python
- OpenCV (`cv2`)
- NumPy

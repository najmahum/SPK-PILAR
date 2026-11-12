# DSS Prioritas Penanganan Jalan (AHP–TOPSIS) - Django

Prototipe Model-driven DSS: bobot kriteria dengan AHP (uji CR ≤ 0.1), peringkat ruas dengan TOPSIS,
seleksi berdasarkan batas anggaran, riwayat dan perbandingan skenario.

## Menjalankan

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo        # opsional: data contoh 4 kriteria + 10 ruas
python manage.py runserver
```

Tes: `python manage.py test`.

## Struktur (Data - Model - Dialog)

| Subsistem | File |
|-----------|------|
| Data (SQLite) | `prioritas/models.py`, impor/ekspor di `views.py` |
| Model | `prioritas/services.py` (`hitung_ahp`, `hitung_topsis`, `pilih_anggaran`, `hitung_semua`) |
| Dialog / UI | `prioritas/views.py`, `prioritas/templates/prioritas/` |

## Alur

1. **Kriteria**: C1 kerusakan, C2 konektivitas, C3 dampak sosial-ekonomi & aduan, C4 keselamatan (rubrik di menu Kriteria).
2. **Ruas Jalan**: input data survei; skor C1 dan C3 dihitung otomatis. Bisa impor CSV/Excel. Tiap ruas punya biaya, serta penanda *darurat* dan *ditunda*.
3. **Perbandingan AHP**: skala Saaty; bobot hanya dipakai jika CR <= 0.1; dibandingkan dengan bobot usulan DPUPR (40/25/20/15).
4. **Peringkat TOPSIS**: isi batas anggaran (opsional). Ruas darurat didanai dulu, ruas ditunda dilewati.
5. **Riwayat Skenario**: snapshot data + bobot + hasil; bandingkan beberapa skenario (what-if).

## Catatan

- Seleksi anggaran bersifat greedy mengikuti peringkat (ruas yang tidak muat dilewati), bukan optimasi knapsack.
- Aplikasi standalone tanpa login. Tambahkan autentikasi Django bila akan dipakai multi-user.
- Chart.js dan Bootstrap dimuat dari CDN (butuh internet saat membuka halaman).
- `SECRET_KEY`/`DEBUG` di `config/settings.py` hanya untuk pengembangan.

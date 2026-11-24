# DSS Prioritas Penanganan Jalan (AHP–TOPSIS)

Prototipe *Model-driven DSS* berbasis Django untuk menentukan prioritas penanganan ruas jalan.
Bobot kriteria dihitung dengan **AHP** (konsisten jika CR ≤ 0,1), peringkat ruas dihitung dengan **TOPSIS**, lalu dipilih sesuai batas anggaran. Mendukung riwayat dan perbandingan skenario.

## Prasyarat

- Python `>=3.13`
- [uv](https://docs.astral.sh/uv/) (disarankan), atau `pip`

## Menjalankan

### Dengan uv (disarankan)

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py seed_demo   # opsional: data contoh 4 kriteria + 10 ruas
uv run python manage.py runserver
```

### Dengan pip

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo   # opsional
python manage.py runserver
```

Aplikasi berjalan di `http://127.0.0.1:8000/`.

## Tes

```bash
uv run python manage.py test
# atau: python manage.py test
```

## Struktur (Data – Model – Dialog)

| Subsistem | File |
|-----------|------|
| Data (SQLite) | `prioritas/models.py`, impor/ekspor di `prioritas/views.py` |
| Model | `prioritas/scoring.py` (rubrik C1–C4), `prioritas/services.py` (`hitung_ahp`, `hitung_topsis`, `pilih_anggaran`, `hitung_semua`) |
| Dialog / UI | `prioritas/views.py`, `prioritas/urls.py`, `prioritas/templates/prioritas/` |

## Alur

1. **Kriteria**: C1 kerusakan, C2 konektivitas, C3 dampak sosial-ekonomi & aduan, C4 keselamatan (rubrik di menu Kriteria).
2. **Ruas Jalan**: input data survei; skor C1 dan C3 dihitung otomatis. Bisa impor/ekspor CSV/Excel. Tiap ruas punya biaya, serta penanda *darurat* dan *ditunda*.
3. **Perbandingan AHP**: skala Saaty; bobot hanya dipakai jika CR ≤ 0,1; dibandingkan dengan bobot usulan DPUPR (40/25/20/15).
4. **Peringkat TOPSIS**: isi batas anggaran (opsional). Ruas darurat didanai dulu, ruas ditunda dilewati.
5. **Riwayat Skenario**: snapshot data + bobot + hasil; bandingkan beberapa skenario (what-if), ekspor CSV.

## Fitur pendukung

- Landing page dan dashboard alur kerja.
- Perbandingan skor antar ruas.
- Impor/ekspor data ruas CSV/XLSX, termasuk templat.
- Ekspor hasil skenario ke CSV.

## Catatan

- Seleksi anggaran bersifat *greedy* mengikuti peringkat (ruas yang tidak muat dilewati), bukan optimasi knapsack.
- Aplikasi standalone tanpa login. Tambahkan autentikasi Django bila akan dipakai multi-user.
- Chart.js dan Bootstrap dimuat dari CDN (butuh internet saat membuka halaman).
- `SECRET_KEY`/`DEBUG` di `config/settings.py` hanya untuk pengembangan.
- `main.py` adalah placeholder; entrypoint aplikasi Django adalah `manage.py`.

"""Rubrik penskoran C1-C4 sesuai dokumen kriteria DPUPR.

Semua fungsi murni (tanpa database) agar mudah diuji dan dijelaskan di laporan.
"""

# Bobot usulan DPUPR, dipakai sebagai pembanding hasil AHP
BOBOT_USULAN = {"C1": 0.40, "C2": 0.25, "C3": 0.20, "C4": 0.15}

SATUAN_BIAYA = "juta Rp"

# ---- C1: Tingkat kerusakan (Permen PU 13/PRT/M/2011, Tabel 1/5/6) ----------
# skor: (kategori, penanganan, mekanisme indikatif)
KATEGORI_KERUSAKAN = {
    1: ("Baik", "Pemeliharaan rutin", "Swakelola"),
    2: ("Ringan", "Pemeliharaan rutin/berkala", "Swakelola / Tim Sapu Lubang"),
    3: ("Sedang", "Rehabilitasi", "Penyedia jasa"),
    4: ("Berat", "Rekonstruksi / peningkatan struktur", "Penyedia jasa"),
}


def skor_kerusakan(persen, berpenutup=True):
    """Persen kerusakan terhadap luas perkerasan -> skor 1..4."""
    if berpenutup:  # Tabel 1/5: <6, 6-11, 11-15, >=15
        batas = (6, 11, 15)
    else:           # Tabel 6: <11, 11-<16, 16-<23, >=23
        batas = (11, 16, 23)
    skor = 1
    for b in batas:
        if persen >= b:
            skor += 1
    return skor


# ---- C2: Konektivitas & fungsi jalan (input manual 1..5) -------------------
OPSI_KONEKTIVITAS = [
    (1, "1 - Lokal rendah: jalan pemukiman/gang kecil, akses terbatas"),
    (2, "2 - Lokal sekunder: antar-pemukiman tanpa fasilitas publik umum"),
    (3, "3 - Konektor fasilitas dasar: akses ke 1 fasilitas dasar (sekolah/puskesmas)"),
    (4, "4 - Konektor sentral: akses utama ke pasar/stasiun atau RS daerah"),
    (5, "5 - Konektor utama/kawasan strategis: pariwisata, pusat kota, jalur antar-wilayah"),
]


# ---- C3: Dampak sosial-ekonomi & aduan (skor tertinggi LHRT vs aduan) ------
def skor_lhrt(lhrt):
    if lhrt > 12000:
        return 5
    if lhrt >= 3000:
        return 4
    if lhrt >= 1000:
        return 3
    if lhrt >= 500:
        return 2
    return 1


def skor_aduan(aduan):
    if aduan > 25:
        return 5
    if aduan >= 11:
        return 4
    if aduan >= 4:
        return 3
    if aduan >= 1:
        return 2
    return 1


def skor_dampak(lhrt, aduan, lumpuh=False):
    if lumpuh:
        return 5
    return max(skor_lhrt(lhrt), skor_aduan(aduan))


# ---- C4: Urgensi keselamatan (input manual 1..5) ---------------------------
OPSI_KESELAMATAN = [
    (1, "1 - Aman: tidak mengganggu stabilitas berkendara"),
    (2, "2 - Rendah: tidak nyaman, berpotensi oleng pada kecepatan tinggi"),
    (3, "3 - Sedang: memaksa pengendara mengerem mendadak / pindah jalur"),
    (4, "4 - Tinggi: lubang dalam (>7 cm) di jalur cepat / sering kecelakaan ringan"),
    (5, "5 - Sangat tinggi/darurat: risiko fatalitas, jalan ambles, genangan parah"),
]

"""Model subsystem (MBMS): AHP, TOPSIS, dan seleksi berdasarkan anggaran.

Semua fungsi inti (hitung_ahp, hitung_topsis, pilih_anggaran) murni Python
tanpa akses database sehingga mudah diuji.
"""
import math

from django.conf import settings

from .scoring import SATUAN_BIAYA

# Random Index Saaty untuk n = 1..15
RI = {
    1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41,
    9: 1.45, 10: 1.49, 11: 1.51, 12: 1.48, 13: 1.56, 14: 1.57, 15: 1.59,
}

MAKNA_SAATY = {
    1: "Sama penting",
    2: "Nilai antara",
    3: "Sedikit lebih penting",
    4: "Nilai antara",
    5: "Lebih penting",
    6: "Nilai antara",
    7: "Sangat lebih penting",
    8: "Nilai antara",
    9: "Mutlak lebih penting",
}


def parse_angka(teks):
    """Terima '12,5' atau '12.5'. Raise ValueError jika bukan angka."""
    teks = str(teks).strip().replace(",", ".")
    if teks == "":
        raise ValueError("kosong")
    nilai = float(teks)
    if math.isnan(nilai) or math.isinf(nilai):
        raise ValueError("bukan angka valid")
    return nilai


def parse_skala(teks):
    """Parse skala Saaty: '3', '1/5'. Harus di antara 1/9 dan 9."""
    teks = str(teks).strip()
    if "/" in teks:
        a, b = teks.split("/")
        nilai = float(a) / float(b)
    else:
        nilai = float(teks)
    if not (1 / 9 - 1e-9 <= nilai <= 9 + 1e-9):
        raise ValueError("skala harus 1/9 sampai 9")
    return nilai


def opsi_skala(kode_a, kode_b):
    """Daftar opsi dropdown untuk pasangan (A, B)."""
    opsi = []
    for n in range(9, 1, -1):
        opsi.append({"val": str(n), "nilai": float(n),
                     "label": f"{kode_a} lebih penting dari {kode_b} ({n}) - {MAKNA_SAATY[n]}"})
    opsi.append({"val": "1", "nilai": 1.0, "label": "Sama penting (1)"})
    for n in range(2, 10):
        opsi.append({"val": f"1/{n}", "nilai": 1 / n,
                     "label": f"{kode_b} lebih penting dari {kode_a} ({n}) - {MAKNA_SAATY[n]}"})
    return opsi


# --------------------------------------------------------------------------
# AHP
# --------------------------------------------------------------------------
def hitung_ahp(matriks, kode=None):
    """Hitung bobot (rata-rata baris matriks ternormalisasi) dan CR."""
    n = len(matriks)
    kode = kode or [f"K{i + 1}" for i in range(n)]
    jumlah_kolom = [sum(matriks[i][j] for i in range(n)) for j in range(n)]
    norm = [[matriks[i][j] / jumlah_kolom[j] for j in range(n)] for i in range(n)]
    bobot = [sum(norm[i]) / n for i in range(n)]

    aw = [sum(matriks[i][j] * bobot[j] for j in range(n)) for i in range(n)]
    lambda_max = sum(aw[i] / bobot[i] for i in range(n)) / n
    ci = max((lambda_max - n) / (n - 1), 0.0) if n > 1 else 0.0
    ri = RI.get(n, 1.59)
    cr = ci / ri if ri > 0 else 0.0

    return {
        "kode": kode,
        "n": n,
        "jumlah_kolom": jumlah_kolom,
        "baris": [
            {"kode": kode[i], "nilai": matriks[i], "norm": norm[i], "bobot": bobot[i]}
            for i in range(n)
        ],
        "bobot": bobot,
        "lambda_max": lambda_max,
        "ci": ci,
        "ri": ri,
        "cr": cr,
        "konsisten": cr <= settings.BATAS_CR + 1e-12,
    }


# --------------------------------------------------------------------------
# TOPSIS
# --------------------------------------------------------------------------
def hitung_topsis(alternatif, jenis, bobot):
    """
    alternatif : list of {"kode","nama","x":[nilai per kriteria]}
    jenis      : list "benefit"/"cost" per kriteria
    bobot      : list bobot per kriteria (jumlah = 1)
    """
    m, n = len(alternatif), len(jenis)

    pembagi = []
    for j in range(n):
        jumlah = sum(a["x"][j] ** 2 for a in alternatif)
        pembagi.append(math.sqrt(jumlah))

    hasil = []
    for a in alternatif:
        r = [(a["x"][j] / pembagi[j]) if pembagi[j] else 0.0 for j in range(n)]
        v = [r[j] * bobot[j] for j in range(n)]
        hasil.append({**a, "r": r, "v": v})

    ideal_plus, ideal_minus = [], []
    for j in range(n):
        kolom = [h["v"][j] for h in hasil]
        if jenis[j] == "benefit":
            ideal_plus.append(max(kolom))
            ideal_minus.append(min(kolom))
        else:
            ideal_plus.append(min(kolom))
            ideal_minus.append(max(kolom))

    for h in hasil:
        h["d_plus"] = math.sqrt(sum((h["v"][j] - ideal_plus[j]) ** 2 for j in range(n)))
        h["d_minus"] = math.sqrt(sum((h["v"][j] - ideal_minus[j]) ** 2 for j in range(n)))
        total = h["d_plus"] + h["d_minus"]
        h["vi"] = h["d_minus"] / total if total else 0.0

    hasil.sort(key=lambda h: (-h["vi"], h["kode"]))
    peringkat_sebelumnya = 0
    for idx, h in enumerate(hasil):
        if idx > 0 and abs(h["vi"] - hasil[idx - 1]["vi"]) < 1e-12:
            h["peringkat"] = peringkat_sebelumnya
        else:
            h["peringkat"] = idx + 1
            peringkat_sebelumnya = h["peringkat"]

    return {
        "pembagi": pembagi,
        "ideal_plus": ideal_plus,
        "ideal_minus": ideal_minus,
        "alternatif": hasil,
    }


def pilih_anggaran(alternatif, batas):
    """Seleksi ruas berdasarkan anggaran tahunan.

    Urutan pendanaan: ruas darurat/agenda khusus lebih dulu, lalu mengikuti peringkat.
    Pemotongan bersifat ketat: begitu satu ruas (non-darurat) tidak muat, semua ruas
    di bawahnya ikut ditunda. Jadi yang tergeser selalu ruas berperingkat paling bawah,
    bukan ruas murah di peringkat bawah yang "menyalip". Sisa anggaran tidak dipakai.
    Ruas yang ditahan (dependensi proyek) dilewati dan tidak memicu pemotongan.

    Mengisi a["terpilih"] dan a["status"]:
    terpilih / luar_anggaran (ditunda karena anggaran) / ditunda (ditahan, dependensi).
    """
    sisa, total, habis = batas, 0.0, False
    urut = sorted(alternatif, key=lambda a: (not a.get("darurat"), a["peringkat"]))
    for a in urut:
        if a.get("ditunda"):
            a["terpilih"], a["status"] = False, "ditunda"
            continue
        biaya = a.get("biaya") or 0.0
        if (not habis or a.get("darurat")) and biaya <= sisa + 1e-9:
            a["terpilih"], a["status"] = True, "terpilih"
            sisa -= biaya
            total += biaya
        else:
            a["terpilih"], a["status"] = False, "luar_anggaran"
            if not a.get("darurat"):
                habis = True
    return total, max(sisa, 0.0)


# --------------------------------------------------------------------------
# Orkestrasi dari database
# --------------------------------------------------------------------------
def muat_ahp():
    """Bangun matriks AHP dari database. Return (kriteria, hasil_ahp | None)."""
    from .models import Kriteria, PerbandinganKriteria

    kriteria = list(Kriteria.objects.all())
    n = len(kriteria)
    if n == 0:
        return kriteria, None
    if n == 1:
        return kriteria, hitung_ahp([[1.0]], [kriteria[0].kode])

    peta = {(p.a_id, p.b_id): p.nilai for p in PerbandinganKriteria.objects.all()}
    m = [[1.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            v = peta.get((kriteria[i].id, kriteria[j].id), 1.0)
            m[i][j] = v
            m[j][i] = 1.0 / v
    return kriteria, hitung_ahp(m, [k.kode for k in kriteria])


def hitung_semua(batas_anggaran=None, tahun=None):
    """Jalankan alur lengkap AHP -> TOPSIS -> seleksi anggaran.

    Raise ValueError dengan pesan ramah jika data belum siap.
    Hasil berupa dict yang aman disimpan sebagai JSON (snapshot skenario).
    """
    from .models import RuasJalan

    kriteria, ahp = muat_ahp()
    if not kriteria:
        raise ValueError("Belum ada kriteria. Tambahkan kriteria terlebih dahulu.")
    if not ahp["konsisten"]:
        raise ValueError(
            f"Matriks perbandingan AHP belum konsisten (CR = {ahp['cr']:.4f} > {settings.BATAS_CR}). "
            "Perbaiki penilaian pada menu Perbandingan AHP."
        )

    ruas_list = list(RuasJalan.objects.prefetch_related("nilai"))
    if len(ruas_list) < 2:
        raise ValueError("Minimal 2 ruas jalan diperlukan untuk pemeringkatan.")

    alternatif = []
    for r in ruas_list:
        peta = {n.kriteria_id: n.nilai for n in r.nilai.all()}
        skor = r.skor_dict()
        alternatif.append({
            "kode": r.kode,
            "nama": r.nama,
            "x": [float(skor.get(k.kode, peta.get(k.id, 0.0))) for k in kriteria],
            "biaya": r.biaya,
            "darurat": r.darurat,
            "ditunda": r.ditunda,
            "persen": r.persen_kerusakan,
            "penanganan": r.kategori_kerusakan[1],
            "mekanisme": r.kategori_kerusakan[2],
        })

    bobot = ahp["bobot"]
    topsis = hitung_topsis(alternatif, [k.jenis for k in kriteria], bobot)

    for a in topsis["alternatif"]:
        a["terpilih"] = None
        a["status"] = "ditunda" if a["ditunda"] else None
    info_anggaran = {"batas": batas_anggaran, "tahun": tahun, "satuan": SATUAN_BIAYA,
                     "total": None, "sisa": None}
    if batas_anggaran is not None:
        total, sisa = pilih_anggaran(topsis["alternatif"], batas_anggaran)
        info_anggaran["total"] = total
        info_anggaran["sisa"] = sisa

    return {
        "kriteria": [
            {"kode": k.kode, "nama": k.nama, "jenis": k.jenis, "satuan": k.satuan,
             "bobot": bobot[i]}
            for i, k in enumerate(kriteria)
        ],
        "ahp": ahp,
        "topsis": {
            "pembagi": topsis["pembagi"],
            "ideal_plus": topsis["ideal_plus"],
            "ideal_minus": topsis["ideal_minus"],
        },
        "alternatif": topsis["alternatif"],
        "anggaran": info_anggaran,
        "grafik": {
            "label": [f"{a['kode']}" for a in topsis["alternatif"]],
            "vi": [round(a["vi"], 6) for a in topsis["alternatif"]],
            "kelas": [
                "darurat" if a["darurat"] else
                ("tidak" if a["status"] in ("luar_anggaran", "ditunda") else "normal")
                for a in topsis["alternatif"]
            ],
        },
    }

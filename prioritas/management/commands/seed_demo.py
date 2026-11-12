from django.core.management.base import BaseCommand
from django.db import transaction

from prioritas.models import Kriteria, PerbandinganKriteria, RuasJalan

KRITERIA = [
    ("C1", "Tingkat kerusakan jalan", "% luas perkerasan",
     "Persen kerusakan terhadap luas perkerasan (Permen PU 13/PRT/M/2011). Skor 1-4."),
    ("C2", "Konektivitas & fungsi jalan", "skor 1-5",
     "Seberapa strategis kawasan yang dihubungkan (PP 34/2006). Skor 1-5."),
    ("C3", "Dampak sosial-ekonomi & aduan publik", "skor 1-5",
     "Skor tertinggi antara LHRT dan jumlah aduan per bulan. Skor 1-5."),
    ("C4", "Urgensi keselamatan", "skor 1-5",
     "Risiko kecelakaan akibat kondisi kerusakan. Skor 1-5."),
]

# kode, nama, permukaan, %rusak, konektivitas, lhrt, aduan, lumpuh, keselamatan, biaya, darurat, ditunda
RUAS = [
    ("R01", "Jl. Slamet Riyadi", "berpenutup", 9, 5, 18000, 12, False, 3, 900, False, False),
    ("R02", "Jl. Adi Sucipto", "berpenutup", 16.5, 4, 14000, 22, False, 4, 1200, False, False),
    ("R03", "Jl. Ahmad Yani (dekat galian utilitas)", "berpenutup", 12, 4, 9000, 8, False, 3, 650, False, True),
    ("R04", "Jl. Kolonel Sugiyono", "berpenutup", 18, 3, 4500, 27, False, 5, 800, True, False),
    ("R05", "Jl. Veteran", "berpenutup", 7, 3, 2500, 5, False, 2, 400, False, False),
    ("R06", "Jl. Mayor Kusmanto", "berpenutup", 4, 3, 1500, 2, False, 1, 250, False, False),
    ("R07", "Jl. Pasar Nongko", "berpenutup", 14, 4, 2800, 15, False, 3, 450, False, False),
    ("R08", "Jl. Lingkar Selatan", "berpenutup", 22, 4, 11000, 30, False, 5, 1500, False, False),
    ("R09", "Jl. Desa Kerten", "tanpa_penutup", 24, 2, 300, 1, False, 2, 200, False, False),
    ("R10", "Jl. Lingkungan Mawar", "tanpa_penutup", 8, 1, 200, 0, False, 1, 60, False, False),
]

# Perbandingan berpasangan (segitiga atas). Hasil bobot mendekati usulan DPUPR 40/25/20/15.
PERBANDINGAN = {
    ("C1", "C2"): 2, ("C1", "C3"): 2, ("C1", "C4"): 3,
    ("C2", "C3"): 2, ("C2", "C4"): 1,
    ("C3", "C4"): 2,
}


class Command(BaseCommand):
    help = "Isi data contoh: 4 kriteria DPUPR, 10 ruas jalan, dan matriks perbandingan AHP."

    @transaction.atomic
    def handle(self, *args, **opts):
        if Kriteria.objects.exists() or RuasJalan.objects.exists():
            self.stdout.write(self.style.WARNING("Data sudah ada, seed dilewati."))
            return
        kriteria = {}
        for i, (kode, nama, satuan, ket) in enumerate(KRITERIA, start=1):
            kriteria[kode] = Kriteria.objects.create(
                kode=kode, nama=nama, jenis="benefit", satuan=satuan, keterangan=ket, urutan=i)
        for (kode, nama, perm, persen, konek, lhrt, aduan, lumpuh, selamat, biaya,
             darurat, ditunda) in RUAS:
            RuasJalan.objects.create(
                kode=kode, nama=nama, jenis_permukaan=perm, persen_kerusakan=persen,
                skor_konektivitas=konek, lhrt=lhrt, aduan_per_bulan=aduan,
                lumpuh_jika_rusak=lumpuh, skor_keselamatan=selamat, biaya=biaya,
                darurat=darurat, ditunda=ditunda)
        for (a, b), v in PERBANDINGAN.items():
            PerbandinganKriteria.objects.create(a=kriteria[a], b=kriteria[b], nilai=v)
        self.stdout.write(self.style.SUCCESS("Data contoh berhasil dibuat."))

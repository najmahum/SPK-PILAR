from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from . import scoring


class Kriteria(models.Model):
    """Metadata kriteria: definisi, jenis (benefit/cost), dan satuan."""

    JENIS = [
        ("benefit", "Benefit (semakin besar semakin diprioritaskan)"),
        ("cost", "Cost (semakin kecil semakin diprioritaskan)"),
    ]

    kode = models.CharField(max_length=10, unique=True)
    nama = models.CharField(max_length=120)
    jenis = models.CharField(max_length=10, choices=JENIS, default="benefit")
    satuan = models.CharField(max_length=40, blank=True)
    keterangan = models.TextField(blank=True)
    urutan = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["urutan", "kode"]
        verbose_name_plural = "Kriteria"

    def __str__(self):
        return f"{self.kode} - {self.nama}"


class RuasJalan(models.Model):
    """Ruas jalan beserta data mentah survei. Skor C1-C4 dihitung dari data ini."""

    PERMUKAAN = [
        ("berpenutup", "Berpenutup (aspal / beton semen)"),
        ("tanpa_penutup", "Tanpa penutup"),
    ]

    kode = models.CharField(max_length=20, unique=True)
    nama = models.CharField(max_length=200)
    keterangan = models.TextField("Keterangan / catatan", blank=True)

    # C1
    jenis_permukaan = models.CharField(max_length=15, choices=PERMUKAAN, default="berpenutup")
    persen_kerusakan = models.FloatField(
        "Kerusakan (% luas perkerasan)", default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)])
    # C2
    skor_konektivitas = models.PositiveSmallIntegerField(
        "Skor konektivitas & fungsi (C2)", choices=scoring.OPSI_KONEKTIVITAS, default=1)
    # C3
    lhrt = models.FloatField("LHRT (smp/hari)", default=0, validators=[MinValueValidator(0)])
    aduan_per_bulan = models.PositiveIntegerField("Aduan publik per bulan", default=0)
    lumpuh_jika_rusak = models.BooleanField("Lalu lintas lumpuh jika rusak", default=False)
    # C4
    skor_keselamatan = models.PositiveSmallIntegerField(
        "Skor urgensi keselamatan (C4)", choices=scoring.OPSI_KESELAMATAN, default=1)

    # Anggaran dan pertimbangan non-model (hasil wawancara DPUPR)
    biaya = models.FloatField("Estimasi biaya penanganan (juta Rp)", default=0,
                              validators=[MinValueValidator(0)])
    darurat = models.BooleanField(
        "Darurat / agenda khusus", default=False,
        help_text="Didanai lebih dulu dalam seleksi anggaran (kerusakan mendadak atau kegiatan tertentu).")
    ditunda = models.BooleanField(
        "Ditunda (dependensi proyek lain)", default=False,
        help_text="Tetap diperingkat, tetapi tidak dipilih dalam seleksi anggaran "
                  "(mis. terdampak kendaraan berat proyek lain atau galian utilitas).")

    class Meta:
        ordering = ["kode"]
        verbose_name_plural = "Ruas jalan"

    def __str__(self):
        return f"{self.kode} - {self.nama}"

    # ---- skor kriteria (dihitung dari data mentah) ----
    @property
    def skor_c1(self):
        return scoring.skor_kerusakan(self.persen_kerusakan, self.jenis_permukaan == "berpenutup")

    @property
    def skor_c2(self):
        return self.skor_konektivitas

    @property
    def skor_c3(self):
        return scoring.skor_dampak(self.lhrt, self.aduan_per_bulan, self.lumpuh_jika_rusak)

    @property
    def skor_c4(self):
        return self.skor_keselamatan

    @property
    def kategori_kerusakan(self):
        return scoring.KATEGORI_KERUSAKAN[self.skor_c1]

    def skor_dict(self):
        return {"C1": self.skor_c1, "C2": self.skor_c2, "C3": self.skor_c3, "C4": self.skor_c4}

    def sinkron_nilai(self):
        """Simpan skor ke tabel NilaiRuas (matriks keputusan)."""
        skor = self.skor_dict()
        for k in Kriteria.objects.filter(kode__in=skor.keys()):
            NilaiRuas.objects.update_or_create(
                ruas=self, kriteria=k, defaults={"nilai": float(skor[k.kode])})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.sinkron_nilai()


class NilaiRuas(models.Model):
    """Skor satu ruas pada satu kriteria (matriks keputusan)."""

    ruas = models.ForeignKey(RuasJalan, on_delete=models.CASCADE, related_name="nilai")
    kriteria = models.ForeignKey(Kriteria, on_delete=models.CASCADE, related_name="nilai")
    nilai = models.FloatField()

    class Meta:
        unique_together = ("ruas", "kriteria")

    def __str__(self):
        return f"{self.ruas.kode}/{self.kriteria.kode} = {self.nilai}"


class PerbandinganKriteria(models.Model):
    """Matriks perbandingan berpasangan AHP (segitiga atas).

    `nilai` = seberapa penting kriteria A dibanding B (skala Saaty 1/9 .. 9).
    """

    a = models.ForeignKey(Kriteria, on_delete=models.CASCADE, related_name="+")
    b = models.ForeignKey(Kriteria, on_delete=models.CASCADE, related_name="+")
    nilai = models.FloatField(default=1.0)

    class Meta:
        unique_together = ("a", "b")


class Skenario(models.Model):
    """Riwayat hasil perhitungan (snapshot lengkap input + hasil)."""

    nama = models.CharField(max_length=150)
    catatan = models.TextField(blank=True)
    dibuat = models.DateTimeField(auto_now_add=True)
    anggaran = models.FloatField(null=True, blank=True)
    cr = models.FloatField(default=0)
    hasil = models.JSONField()

    class Meta:
        ordering = ["-dibuat"]
        verbose_name_plural = "Skenario"

    def __str__(self):
        return self.nama

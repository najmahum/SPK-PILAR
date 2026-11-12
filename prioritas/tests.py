from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from . import scoring
from .models import RuasJalan, Skenario
from .services import hitung_ahp, hitung_semua, hitung_topsis, pilih_anggaran


class ScoringTest(TestCase):
    def test_kerusakan_berpenutup(self):
        f = scoring.skor_kerusakan
        self.assertEqual([f(x) for x in (0, 5.9, 6, 10.9, 11, 14.9, 15, 40)],
                         [1, 1, 2, 2, 3, 3, 4, 4])

    def test_kerusakan_tanpa_penutup(self):
        f = lambda x: scoring.skor_kerusakan(x, berpenutup=False)  # noqa: E731
        self.assertEqual([f(x) for x in (10.9, 11, 15.9, 16, 22.9, 23)], [1, 2, 2, 3, 3, 4])

    def test_dampak_ambil_skor_tertinggi(self):
        self.assertEqual(scoring.skor_lhrt(499), 1)
        self.assertEqual(scoring.skor_lhrt(3000), 4)
        self.assertEqual(scoring.skor_lhrt(12000), 4)
        self.assertEqual(scoring.skor_lhrt(12001), 5)
        self.assertEqual(scoring.skor_aduan(0), 1)
        self.assertEqual(scoring.skor_aduan(3), 2)
        self.assertEqual(scoring.skor_aduan(10), 3)
        self.assertEqual(scoring.skor_aduan(25), 4)
        self.assertEqual(scoring.skor_aduan(26), 5)
        self.assertEqual(scoring.skor_dampak(600, 12), 4)   # max(2, 4)
        self.assertEqual(scoring.skor_dampak(100, 0, lumpuh=True), 5)


class AhpTopsisTest(TestCase):
    def test_ahp_matriks_konsisten_sempurna(self):
        m = [[1, 2, 2], [0.5, 1, 1], [0.5, 1, 1]]
        h = hitung_ahp(m)
        self.assertAlmostEqual(sum(h["bobot"]), 1.0)
        self.assertAlmostEqual(h["bobot"][0], 0.5)
        self.assertAlmostEqual(h["cr"], 0.0, places=6)

    def test_ahp_tidak_konsisten(self):
        m = [[1, 9, 1 / 9], [1 / 9, 1, 9], [9, 1 / 9, 1]]
        self.assertFalse(hitung_ahp(m)["konsisten"])

    def test_anggaran_darurat_dulu_dan_ditunda_dilewati(self):
        alt = [
            {"kode": "A", "nama": "A", "x": [10.0, 5.0]},
            {"kode": "B", "nama": "B", "x": [8.0, 4.0]},
            {"kode": "C", "nama": "C", "x": [2.0, 1.0]},
        ]
        a = hitung_topsis(alt, ["benefit", "benefit"], [0.6, 0.4])["alternatif"]
        for x in a:
            x.update(biaya=50.0, darurat=x["kode"] == "C", ditunda=x["kode"] == "A")
        total, sisa = pilih_anggaran(a, 100)
        st = {x["kode"]: x["status"] for x in a}
        self.assertEqual(st, {"A": "ditunda", "B": "terpilih", "C": "terpilih"})
        self.assertAlmostEqual(total, 100.0)
        self.assertAlmostEqual(sisa, 0.0)

        # darurat didahulukan ketika anggaran hanya cukup untuk satu ruas
        for x in a:
            x.pop("status", None)
        pilih_anggaran(a, 50)
        st = {x["kode"]: x["status"] for x in a}
        self.assertEqual(st["C"], "terpilih")
        self.assertEqual(st["B"], "luar_anggaran")


    def test_potong_ketat_yang_tergeser_peringkat_bawah(self):
        # Peringkat 1..4, biaya 40,60,30,10; anggaran 100. R3 (30) tidak boleh menyalip
        # karena R2 (60) sudah tidak muat setelah R1 (40)+... urutan: 40, 60 (=100), lalu stop.
        alt = [{"kode": f"R{i}", "nama": "x", "peringkat": i, "biaya": b,
                "darurat": False, "ditunda": False}
               for i, b in enumerate([40.0, 70.0, 30.0, 10.0], start=1)]
        pilih_anggaran(alt, 100)
        st = [a["status"] for a in alt]
        self.assertEqual(st, ["terpilih", "luar_anggaran", "luar_anggaran", "luar_anggaran"])

    def test_darurat_menggeser_peringkat_paling_bawah(self):
        alt = [{"kode": f"R{i}", "nama": "x", "peringkat": i, "biaya": 40.0,
                "darurat": i == 4, "ditunda": False} for i in range(1, 5)]
        pilih_anggaran(alt, 120)   # cukup untuk 3 ruas: darurat R4 + R1 + R2
        st = {a["kode"]: a["status"] for a in alt}
        self.assertEqual(st, {"R4": "terpilih", "R1": "terpilih", "R2": "terpilih",
                              "R3": "luar_anggaran"})


class AlurTest(TestCase):
    def setUp(self):
        call_command("seed_demo", verbosity=0)

    def test_skor_tersinkron_ke_matriks_keputusan(self):
        r = RuasJalan.objects.get(kode="R04")   # 18% -> 4, konek 3, aduan 27 -> 5, selamat 5
        self.assertEqual(r.skor_dict(), {"C1": 4, "C2": 3, "C3": 5, "C4": 5})
        self.assertEqual(sorted(n.nilai for n in r.nilai.all()), [3.0, 4.0, 5.0, 5.0])

    def test_hitung_semua(self):
        h = hitung_semua(3500)
        self.assertTrue(h["ahp"]["konsisten"])
        self.assertEqual(len(h["alternatif"]), 10)
        self.assertLessEqual(h["anggaran"]["total"], 3500)
        st = {a["kode"]: a["status"] for a in h["alternatif"]}
        self.assertEqual(st["R03"], "ditunda")
        self.assertEqual(st["R04"], "terpilih")   # darurat

    def test_halaman_dan_skenario(self):
        for nama in ["dashboard", "kriteria_list", "ruas_list", "ruas_tambah", "ruas_bandingkan",
                     "data_impor", "ahp", "topsis", "skenario_list"]:
            self.assertEqual(self.client.get(reverse(nama)).status_code, 200, nama)
        self.assertEqual(self.client.get(reverse("ruas_ubah", args=[1])).status_code, 200)
        self.assertEqual(self.client.get(reverse("kriteria_ubah", args=[1])).status_code, 200)

        r = self.client.post(reverse("topsis"), {"anggaran": "3500", "tahun": "2027"})
        self.assertContains(r, "Peringkat prioritas penanganan")
        self.assertContains(r, "tahun 2027")
        self.assertContains(r, "Kolonel Sugiyono")

        self.client.post(reverse("skenario_simpan"), {"anggaran": "3500", "nama": "S1"})
        self.client.post(reverse("skenario_simpan"), {"anggaran": "2000", "nama": "S2"})
        s1, s2 = Skenario.objects.order_by("id")
        self.assertEqual(self.client.get(reverse("skenario_detail", args=[s1.pk])).status_code, 200)
        r = self.client.get(reverse("skenario_bandingkan"), {"id": [s1.pk, s2.pk]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(reverse("skenario_ekspor", args=[s1.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("data_ekspor", args=["csv"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("data_ekspor", args=["xlsx"])).status_code, 200)

    def test_tambah_ruas_via_form(self):
        r = self.client.post(reverse("ruas_tambah"), {
            "kode": "R99", "nama": "Uji", "jenis_permukaan": "berpenutup",
            "persen_kerusakan": "12", "skor_konektivitas": "2", "lhrt": "700",
            "aduan_per_bulan": "0", "skor_keselamatan": "1", "biaya": "100"})
        self.assertEqual(r.status_code, 302)
        r = RuasJalan.objects.get(kode="R99")
        self.assertEqual(r.skor_dict(), {"C1": 3, "C2": 2, "C3": 2, "C4": 1})

    def test_impor_csv(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        csv_isi = ("kode;nama;persen_kerusakan;skor_konektivitas;lhrt;aduan_per_bulan;"
                   "skor_keselamatan;biaya\nR50;Impor Satu;20;3;5000;12;4;300\n"
                   "R51;Rusak;abc;3;5000;12;4;300\n")
        f = SimpleUploadedFile("d.csv", csv_isi.encode(), content_type="text/csv")
        self.client.post(reverse("data_impor"), {"berkas": f})
        self.assertTrue(RuasJalan.objects.filter(kode="R50").exists())
        self.assertFalse(RuasJalan.objects.filter(kode="R51").exists())
        self.assertEqual(RuasJalan.objects.get(kode="R50").skor_c3, 4)

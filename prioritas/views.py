import csv
import io
from collections import OrderedDict

from django import forms
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Kriteria, PerbandinganKriteria, RuasJalan, Skenario
from .scoring import BOBOT_USULAN
from .services import (hitung_semua, muat_ahp, opsi_skala, parse_angka,
                       parse_skala)


# ---------------------------------------------------------------- Dashboard
def dashboard(request):
    kriteria, ahp = muat_ahp()
    konteks = {
        "jumlah_kriteria": len(kriteria),
        "jumlah_ruas": RuasJalan.objects.count(),
        "jumlah_skenario": Skenario.objects.count(),
        "ahp": ahp,
        "batas_cr": settings.BATAS_CR,
        "skenario_terbaru": Skenario.objects.all()[:5],
        "ruas_darurat": RuasJalan.objects.filter(darurat=True),
        "ruas_ditunda": RuasJalan.objects.filter(ditunda=True),
    }
    return render(request, "prioritas/dashboard.html", konteks)


# ----------------------------------------------------------------- Kriteria
class KriteriaForm(forms.ModelForm):
    class Meta:
        model = Kriteria
        fields = ["nama", "satuan", "keterangan"]
        widgets = {"keterangan": forms.Textarea(attrs={"rows": 3})}


def kriteria_list(request):
    from . import scoring
    return render(request, "prioritas/kriteria_list.html", {
        "daftar": Kriteria.objects.all(),
        "bobot_usulan": BOBOT_USULAN,
        "kerusakan": scoring.KATEGORI_KERUSAKAN,
        "opsi_konek": scoring.OPSI_KONEKTIVITAS,
        "opsi_selamat": scoring.OPSI_KESELAMATAN,
    })


def kriteria_form(request, pk):
    obj = get_object_or_404(Kriteria, pk=pk)
    form = KriteriaForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Kriteria disimpan.")
        return redirect("kriteria_list")
    return render(request, "prioritas/form_umum.html",
                  {"form": form, "judul": f"Ubah kriteria {obj.kode}", "kembali": "kriteria_list"})


# --------------------------------------------------------------------- Ruas
class RuasForm(forms.ModelForm):
    class Meta:
        model = RuasJalan
        fields = ["kode", "nama", "jenis_permukaan", "persen_kerusakan",
                  "skor_konektivitas", "lhrt", "aduan_per_bulan", "lumpuh_jika_rusak",
                  "skor_keselamatan", "biaya", "darurat", "ditunda", "keterangan"]
        widgets = {"keterangan": forms.Textarea(attrs={"rows": 2})}
        labels = {"ditunda": "Ditahan (dependensi proyek lain)"}
        help_texts = {
            "darurat": "Didanai lebih dulu, mis. kerusakan mendadak atau ada kegiatan penting. "
                       "Ruas lain yang paling bawah peringkatnya bergeser kalau anggaran tidak cukup.",
            "ditunda": "Tetap diperingkat, tapi tidak dimasukkan ke anggaran tahun ini "
                       "(mis. terdampak kendaraan berat proyek lain atau galian utilitas).",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            w = f.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs["class"] = "form-check-input"
            elif isinstance(w, forms.Select):
                w.attrs["class"] = "form-select"
            else:
                w.attrs["class"] = "form-control"
            if isinstance(w, forms.NumberInput):
                w.attrs["step"] = "any"


def ruas_list(request):
    return render(request, "prioritas/ruas_list.html", {"daftar": RuasJalan.objects.all()})


def ruas_form(request, pk=None):
    obj = get_object_or_404(RuasJalan, pk=pk) if pk else None
    form = RuasForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Ruas jalan disimpan. Skor C1-C4 dihitung otomatis.")
        return redirect("ruas_list")
    return render(request, "prioritas/ruas_form.html", {"form": form, "obj": obj})


def ruas_hapus(request, pk):
    obj = get_object_or_404(RuasJalan, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Ruas jalan dihapus.")
        return redirect("ruas_list")
    return render(request, "prioritas/konfirmasi_hapus.html", {"obj": obj, "kembali": "ruas_list"})


def ruas_bandingkan(request):
    """Perbandingan skor kriteria antar ruas yang dipilih (tabel + grafik)."""
    semua = list(RuasJalan.objects.all())
    kriteria = list(Kriteria.objects.all())
    dipilih_id = {int(i) for i in request.GET.getlist("id") if i.isdigit()}
    dipilih = [r for r in semua if r.id in dipilih_id]

    grafik, tabel = None, []
    if dipilih:
        kode = [k.kode for k in kriteria]
        for r in dipilih:
            skor = r.skor_dict()
            tabel.append({"ruas": r, "nilai": [skor.get(c) for c in kode]})
        grafik = {
            "labels": kode,
            "datasets": [{"label": b["ruas"].kode, "data": b["nilai"]} for b in tabel],
        }
    return render(request, "prioritas/ruas_bandingkan.html", {
        "semua": semua, "kriteria": kriteria, "dipilih_id": dipilih_id,
        "tabel": tabel, "grafik": grafik})


# --------------------------------------------------------------- Impor/ekspor
KOLOM_DATA = ["kode", "nama", "jenis_permukaan", "persen_kerusakan", "skor_konektivitas",
              "lhrt", "aduan_per_bulan", "lumpuh_jika_rusak", "skor_keselamatan", "biaya",
              "darurat", "ditunda"]
KOLOM_WAJIB = ["kode", "nama", "persen_kerusakan", "skor_konektivitas", "lhrt",
               "aduan_per_bulan", "skor_keselamatan", "biaya"]


def _ya_tidak(v):
    return "ya" if v else "tidak"


def _baris_data():
    isi = []
    for r in RuasJalan.objects.all():
        isi.append([r.kode, r.nama, r.jenis_permukaan, r.persen_kerusakan, r.skor_konektivitas,
                    r.lhrt, r.aduan_per_bulan, _ya_tidak(r.lumpuh_jika_rusak),
                    r.skor_keselamatan, r.biaya, _ya_tidak(r.darurat), _ya_tidak(r.ditunda)])
    return KOLOM_DATA, isi


def data_ekspor(request, fmt):
    header, isi = _baris_data()
    if request.GET.get("templat"):
        isi = [["R01", "Contoh Jl. Merdeka", "berpenutup", 12.5, 3, 4200, 8, "tidak", 3, 450,
                "tidak", "tidak"]]
    if fmt == "xlsx":
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Ruas Jalan"
        ws.append(header)
        for baris in isi:
            ws.append(baris)
        buf = io.BytesIO()
        wb.save(buf)
        resp = HttpResponse(buf.getvalue(),
                            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = 'attachment; filename="data_ruas_jalan.xlsx"'
        return resp
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="data_ruas_jalan.csv"'
    resp.write("\ufeff")
    w = csv.writer(resp)
    w.writerow(header)
    w.writerows(isi)
    return resp


def _baca_file(berkas):
    nama = berkas.name.lower()
    if nama.endswith(".xlsx"):
        from openpyxl import load_workbook
        ws = load_workbook(berkas, read_only=True, data_only=True).active
        return [["" if c is None else c for c in row] for row in ws.iter_rows(values_only=True)]
    teks = berkas.read().decode("utf-8-sig")
    try:
        dialek = csv.Sniffer().sniff(teks[:2000], delimiters=",;\t")
    except csv.Error:
        dialek = csv.excel
    return list(csv.reader(io.StringIO(teks), dialek))


def _bool(v):
    return str(v).strip().lower() in {"ya", "y", "1", "true", "benar", "x"}


def _int_skor(v, nama):
    n = parse_angka(v)
    if n != int(n) or not 1 <= n <= 5:
        raise ValueError(f"{nama} harus bilangan bulat 1-5")
    return int(n)


def data_impor(request):
    if request.method == "POST" and request.FILES.get("berkas"):
        try:
            baris = _baca_file(request.FILES["berkas"])
        except Exception as e:  # noqa: BLE001 - tampilkan pesan ramah
            messages.error(request, f"Berkas tidak bisa dibaca: {e}")
            return redirect("data_impor")
        if not baris:
            messages.error(request, "Berkas kosong.")
            return redirect("data_impor")

        header = [str(h).strip().lower() for h in baris[0]]
        hilang = [k for k in KOLOM_WAJIB if k not in header]
        if hilang:
            messages.error(request, "Kolom wajib tidak ditemukan: " + ", ".join(hilang))
            return redirect("data_impor")
        idx = {k: header.index(k) for k in KOLOM_DATA if k in header}

        def ambil(row, k, default=""):
            return row[idx[k]] if k in idx and idx[k] < len(row) else default

        sukses, galat = 0, []
        with transaction.atomic():
            for no, row in enumerate(baris[1:], start=2):
                if not any(str(c).strip() for c in row):
                    continue
                try:
                    kode, nama = str(ambil(row, "kode")).strip(), str(ambil(row, "nama")).strip()
                    if not kode or not nama:
                        raise ValueError("kode/nama kosong")
                    permukaan = str(ambil(row, "jenis_permukaan", "berpenutup")).strip().lower()
                    permukaan = "tanpa_penutup" if permukaan.replace(" ", "_") == "tanpa_penutup" else "berpenutup"
                    persen = parse_angka(ambil(row, "persen_kerusakan"))
                    if not 0 <= persen <= 100:
                        raise ValueError("persen_kerusakan harus 0-100")
                    lhrt = parse_angka(ambil(row, "lhrt"))
                    aduan = parse_angka(ambil(row, "aduan_per_bulan"))
                    biaya = parse_angka(ambil(row, "biaya"))
                    if lhrt < 0 or aduan < 0 or biaya < 0:
                        raise ValueError("lhrt, aduan, dan biaya tidak boleh negatif")
                    data = {
                        "nama": nama, "jenis_permukaan": permukaan, "persen_kerusakan": persen,
                        "skor_konektivitas": _int_skor(ambil(row, "skor_konektivitas"), "skor_konektivitas"),
                        "lhrt": lhrt, "aduan_per_bulan": int(aduan),
                        "lumpuh_jika_rusak": _bool(ambil(row, "lumpuh_jika_rusak")),
                        "skor_keselamatan": _int_skor(ambil(row, "skor_keselamatan"), "skor_keselamatan"),
                        "biaya": biaya, "darurat": _bool(ambil(row, "darurat")),
                        "ditunda": _bool(ambil(row, "ditunda")),
                    }
                except (ValueError, IndexError) as e:
                    galat.append(f"Baris {no}: {e}")
                    continue
                obj = RuasJalan.objects.filter(kode=kode).first() or RuasJalan(kode=kode)
                for k, v in data.items():
                    setattr(obj, k, v)
                obj.save()
                sukses += 1
        messages.success(request, f"{sukses} ruas jalan berhasil diimpor/diperbarui.")
        for g in galat[:10]:
            messages.warning(request, g)
        return redirect("ruas_list")
    return render(request, "prioritas/impor.html",
                  {"kolom": KOLOM_DATA, "wajib": KOLOM_WAJIB})


# ---------------------------------------------------------------------- AHP
def ahp_view(request):
    kriteria = list(Kriteria.objects.all())

    if request.method == "POST":
        tersimpan = 0
        for i, a in enumerate(kriteria):
            for b in kriteria[i + 1:]:
                mentah = request.POST.get(f"p_{a.id}_{b.id}")
                if mentah is None:
                    continue
                try:
                    nilai = parse_skala(mentah)
                except (ValueError, ZeroDivisionError):
                    messages.error(request, f"Nilai {a.kode} vs {b.kode} tidak valid.")
                    continue
                PerbandinganKriteria.objects.update_or_create(a=a, b=b, defaults={"nilai": nilai})
                tersimpan += 1
        _, hasil = muat_ahp()
        if hasil and hasil["konsisten"]:
            messages.success(request, f"Penilaian disimpan. CR = {hasil['cr']:.4f} (konsisten, bobot dipakai).")
        elif hasil:
            messages.warning(request, f"Penilaian disimpan, tetapi CR = {hasil['cr']:.4f} melebihi "
                                      f"{settings.BATAS_CR}. Perbaiki penilaian sebelum menghitung TOPSIS.")
        return redirect("ahp")

    kriteria, hasil = muat_ahp()
    pembanding = []
    if hasil:
        for b in hasil["baris"]:
            usulan = BOBOT_USULAN.get(b["kode"])
            pembanding.append({
                "kode": b["kode"], "ahp": b["bobot"], "usulan": usulan,
                "selisih": None if usulan is None else (b["bobot"] - usulan) * 100})
    peta = {(p.a_id, p.b_id): p.nilai for p in PerbandinganKriteria.objects.all()}
    pasangan = []
    for i, a in enumerate(kriteria):
        for b in kriteria[i + 1:]:
            nilai = peta.get((a.id, b.id), 1.0)
            opsi = opsi_skala(a.kode, b.kode)
            terdekat = min(opsi, key=lambda o: abs(o["nilai"] - nilai))
            for o in opsi:
                o["dipilih"] = o is terdekat
            pasangan.append({"a": a, "b": b, "opsi": opsi})

    return render(request, "prioritas/ahp.html", {
        "kriteria": kriteria, "pasangan": pasangan, "ahp": hasil,
        "pembanding": pembanding, "batas_cr": settings.BATAS_CR})


# ------------------------------------------------------------------- TOPSIS
def _parse_anggaran(teks):
    teks = (teks or "").strip()
    if not teks:
        return None
    nilai = parse_angka(teks)
    if nilai < 0:
        raise ValueError("Anggaran tidak boleh negatif.")
    return nilai


def topsis_view(request):
    hasil, galat, anggaran_str, tahun = None, None, "", ""
    darurat, ditunda = [], []
    if request.method == "POST":
        anggaran_str = request.POST.get("anggaran", "")
        tahun = request.POST.get("tahun", "").strip()
        try:
            hasil = hitung_semua(_parse_anggaran(anggaran_str), tahun or None)
            darurat = [a for a in hasil["alternatif"] if a["darurat"]]
            ditunda = [a for a in hasil["alternatif"] if a["ditunda"]]
        except ValueError as e:
            galat = str(e)
    return render(request, "prioritas/topsis.html", {
        "hasil": hasil, "galat": galat, "anggaran_str": anggaran_str, "tahun": tahun,
        "darurat": darurat, "ditunda": ditunda})


@require_POST
def skenario_simpan(request):
    try:
        batas = _parse_anggaran(request.POST.get("anggaran"))
        hasil = hitung_semua(batas, request.POST.get("tahun", "").strip() or None)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("topsis")
    nama = request.POST.get("nama", "").strip() or "Skenario tanpa nama"
    skenario = Skenario.objects.create(
        nama=nama, catatan=request.POST.get("catatan", "").strip(),
        anggaran=batas, cr=hasil["ahp"]["cr"], hasil=hasil)
    messages.success(request, "Skenario disimpan ke riwayat.")
    return redirect("skenario_detail", pk=skenario.pk)


# ----------------------------------------------------------------- Skenario
def skenario_list(request):
    return render(request, "prioritas/skenario_list.html", {"daftar": Skenario.objects.all()})


def skenario_detail(request, pk):
    s = get_object_or_404(Skenario, pk=pk)
    return render(request, "prioritas/skenario_detail.html", {"s": s, "hasil": s.hasil})


def skenario_hapus(request, pk):
    s = get_object_or_404(Skenario, pk=pk)
    if request.method == "POST":
        s.delete()
        messages.success(request, "Skenario dihapus.")
        return redirect("skenario_list")
    return render(request, "prioritas/konfirmasi_hapus.html", {"obj": s, "kembali": "skenario_list"})


def skenario_ekspor(request, pk):
    s = get_object_or_404(Skenario, pk=pk)
    h = s.hasil
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="skenario_{s.pk}.csv"'
    resp.write("﻿")
    w = csv.writer(resp)
    kode_k = [k["kode"] for k in h["kriteria"]]
    w.writerow(["peringkat", "kode", "nama", "Vi", "D+", "D-", "biaya", "status"] + kode_k)
    for a in h["alternatif"]:
        terpilih = a.get("status") or ""
        w.writerow([a["peringkat"], a["kode"], a["nama"], round(a["vi"], 6),
                    round(a["d_plus"], 6), round(a["d_minus"], 6),
                    "" if a["biaya"] is None else a["biaya"], terpilih] + a["x"])
    return resp


def skenario_bandingkan(request):
    ids = [int(i) for i in request.GET.getlist("id") if i.isdigit()]
    skenario = list(Skenario.objects.filter(id__in=ids).order_by("dibuat"))
    if len(skenario) < 2:
        messages.warning(request, "Pilih minimal dua skenario untuk dibandingkan.")
        return redirect("skenario_list")

    # Bobot kriteria antarversi
    kode_kriteria = OrderedDict()
    for s in skenario:
        for k in s.hasil["kriteria"]:
            kode_kriteria.setdefault(k["kode"], k["nama"])
    tabel_bobot = []
    for kode, nama in kode_kriteria.items():
        baris = []
        for s in skenario:
            bobot = next((k["bobot"] for k in s.hasil["kriteria"] if k["kode"] == kode), None)
            baris.append(bobot)
        tabel_bobot.append({"kode": kode, "nama": nama, "bobot": baris})

    # Peringkat antarskenario
    ruas = OrderedDict()
    for s in skenario:
        for a in s.hasil["alternatif"]:
            ruas.setdefault(a["kode"], {"kode": a["kode"], "nama": a["nama"], "data": []})
    for kode, item in ruas.items():
        for s in skenario:
            a = next((x for x in s.hasil["alternatif"] if x["kode"] == kode), None)
            item["data"].append(a)
        ada = [d["peringkat"] for d in item["data"] if d]
        item["berubah"] = len(set(ada)) > 1 or len(ada) != len(skenario)
    tabel_peringkat = sorted(
        ruas.values(),
        key=lambda r: (r["data"][0]["peringkat"] if r["data"][0] else 999, r["kode"]))

    grafik = {
        "labels": [r["kode"] for r in tabel_peringkat],
        "datasets": [
            {"label": s.nama,
             "data": [round(r["data"][i]["vi"], 6) if r["data"][i] else None
                      for r in tabel_peringkat]}
            for i, s in enumerate(skenario)
        ],
    }
    return render(request, "prioritas/skenario_bandingkan.html", {
        "skenario": skenario, "tabel_bobot": tabel_bobot,
        "tabel_peringkat": tabel_peringkat, "grafik": grafik})

from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("kriteria/", views.kriteria_list, name="kriteria_list"),
    path("kriteria/<int:pk>/ubah/", views.kriteria_form, name="kriteria_ubah"),

    path("ruas/", views.ruas_list, name="ruas_list"),
    path("ruas/tambah/", views.ruas_form, name="ruas_tambah"),
    path("ruas/<int:pk>/ubah/", views.ruas_form, name="ruas_ubah"),
    path("ruas/<int:pk>/hapus/", views.ruas_hapus, name="ruas_hapus"),
    path("ruas/bandingkan/", views.ruas_bandingkan, name="ruas_bandingkan"),
    path("data/impor/", views.data_impor, name="data_impor"),
    path("data/ekspor/<str:fmt>/", views.data_ekspor, name="data_ekspor"),

    path("ahp/", views.ahp_view, name="ahp"),
    path("topsis/", views.topsis_view, name="topsis"),

    path("skenario/", views.skenario_list, name="skenario_list"),
    path("skenario/simpan/", views.skenario_simpan, name="skenario_simpan"),
    path("skenario/bandingkan/", views.skenario_bandingkan, name="skenario_bandingkan"),
    path("skenario/<int:pk>/", views.skenario_detail, name="skenario_detail"),
    path("skenario/<int:pk>/hapus/", views.skenario_hapus, name="skenario_hapus"),
    path("skenario/<int:pk>/ekspor/", views.skenario_ekspor, name="skenario_ekspor"),
]

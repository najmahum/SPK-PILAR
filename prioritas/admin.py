from django.contrib import admin

from .models import Kriteria, NilaiRuas, PerbandinganKriteria, RuasJalan, Skenario

admin.site.register(Kriteria)
admin.site.register(RuasJalan)
admin.site.register(NilaiRuas)
admin.site.register(PerbandinganKriteria)
admin.site.register(Skenario)

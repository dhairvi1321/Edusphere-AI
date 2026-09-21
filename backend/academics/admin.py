from django.contrib import admin
from .models import Subject, SyllabusTopic, Assignment, Exam

admin.site.register(Subject)
admin.site.register(SyllabusTopic)
admin.site.register(Assignment)
admin.site.register(Exam)

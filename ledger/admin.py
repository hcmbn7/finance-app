from django.contrib import admin

from .models import Account, Category, ImportBatch, Institution, Transaction

admin.site.register(Institution)
admin.site.register(Account)
admin.site.register(Category)
admin.site.register(ImportBatch)
admin.site.register(Transaction)

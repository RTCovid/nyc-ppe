from django.contrib import admin

# Register your models here.
from ppe.models import FailedImport


def retry_upload(_modeladmin, _request, queryset):
    queryset.first().retry()


retry_upload.short_description = "Retry a failed upload"


class FailedImportAdmin(admin.ModelAdmin):
    actions = [retry_upload]


admin.site.register(FailedImport, FailedImportAdmin)

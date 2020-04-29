from django.contrib import admin

# Register your models here.
from ppe.models import FailedImport, DataImport


def retry_upload(_modeladmin, _request, queryset):
    queryset.first().retry()


retry_upload.short_description = "Retry a failed upload"


class FailedImportAdmin(admin.ModelAdmin):
    actions = [retry_upload]


class DataImportAdmin(admin.ModelAdmin):
    list_display = (
        "import_date",
        "status",
        "current_as_of",
        "uploaded_by",
        "file_name",
    )
    ordering = ("status",)


admin.site.register(FailedImport, FailedImportAdmin)
admin.site.register(DataImport, DataImportAdmin)

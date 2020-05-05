from django.conf.urls import url
from django.contrib import admin

# Register your models here.
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html

from ppe.models import FailedImport, DataImport


def retry_upload(_modeladmin, _request, queryset):
    queryset.first().retry()


retry_upload.short_description = "Retry a failed upload"


class FailedImportAdmin(admin.ModelAdmin):
    actions = [retry_upload]
    list_display = (
        "file_name",
        "uploaded_at",
        "uploaded_by",
        "current_as_of",
        "fixed",
        "download"
    )
    readonly_fields = ('download',)

    DOWNLOAD_NAME = 'ppe_failedimport_download'

    # add custom view to urls
    def get_urls(self):
        urls = super().get_urls()
        urls += [
            url(r'^download-file/(?P<pk>\d+)$', self.download_file, 
                name=self.DOWNLOAD_NAME),
        ]
        return urls

    # custom "field" that returns a link to the custom function
    def download(self, obj):
        return format_html(
            '<a href="{}">Download file</a>',
            reverse(f'admin:{self.DOWNLOAD_NAME}', args=[obj.pk])
        )
    download.short_description = "Download file"

    # add custom view function that downloads the file
    def download_file(self, request, pk):
        response = HttpResponse(content_type='application/force-download')
        obj: FailedImport = FailedImport.objects.get(id=pk)
        response['Content-Disposition'] = f'attachment; filename="{obj.file_name}"'
        # generate dynamic file content using object pk
        response.write(obj.data)
        return response


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

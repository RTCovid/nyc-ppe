from django import forms


class UploadFileForm(forms.Form):
    file = forms.FileField()
    data_current = forms.DateField(label="Data current as of YYYY-MM-DD")

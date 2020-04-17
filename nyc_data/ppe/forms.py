from django import forms


class UploadFileForm(forms.Form):
    file = forms.FileField()
    name = forms.CharField(label="Your name")
    data_current = forms.DateField(label="Data current as of YYYY-MM-DD")

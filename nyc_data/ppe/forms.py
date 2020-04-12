from django import forms

class UploadFileForm(forms.Form):
    file = forms.FileField()
    name = forms.CharField(label='Your name')
    notes = forms.Textarea()


# uploader/forms.py
from django import forms
from .models import UploadedFile

class UploadForm(forms.Form):
    file = forms.FileField()
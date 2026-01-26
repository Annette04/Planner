# uploader/models.py
from django.db import models

class UploadedFile(models.Model):
    type = models.CharField(max_length=50)  # 'plan', 'changes', 'schedule', 'materials'
    file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    headers = models.JSONField(null=True, blank=True)  # Заголовки колонок

    def __str__(self):
        return f"{self.type}: {self.file.name}"
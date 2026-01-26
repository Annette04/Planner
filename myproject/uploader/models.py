from django.db import models

class UploadedFile(models.Model):
    file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    #храним заголовки колонок для удобства (список в JSON)
    headers = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.file.name

class ImportedRow(models.Model):
    file = models.ForeignKey(UploadedFile, on_delete=models.CASCADE, related_name='rows')
    row_data = models.JSONField()  # {"Имя": "Анна", "Роль": "Разработчик", ...}
    row_number = models.PositiveIntegerField()  # Номер строки для сортировки

    class Meta:
        unique_together = ['file', 'row_number']
        ordering = ['row_number']

    def __str__(self):
        return f"Row {self.row_number} of {self.file}"
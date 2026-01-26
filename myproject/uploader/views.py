# uploader/views.py
import pandas as pd
from django.shortcuts import render, redirect
from django.db import connection, models as django_models
from django.apps import apps
from .forms import UploadForm
from .models import UploadedFile


def home(request):
    return render(request, 'uploader/home.html')


def upload(request, file_type):
    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            # Сохраняем файл временно
            uploaded_file = UploadedFile.objects.create(type=file_type, file=file)
            process_excel_to_db(uploaded_file, file_type)
            return redirect('success', file_type=file_type)
    else:
        form = UploadForm()
    return render(request, 'uploader/upload.html', {'form': form, 'file_type': file_type})


def process_excel_to_db(uploaded_file, file_type):
    file_path = uploaded_file.file.path
    df = pd.read_excel(file_path)
    headers = df.columns.tolist()
    uploaded_file.headers = headers
    uploaded_file.save()

    app_label = 'uploader'
    model_name = file_type.capitalize()  # Plan, Changes, etc.
    table_name = f"uploader_{file_type}"

    try:
        DynamicModel = apps.get_model(app_label, model_name)
        # Проверяем совпадение заголовков
        existing_fields = [f.name for f in DynamicModel._meta.get_fields() if f.name != 'id']
        if sorted(existing_fields) != sorted(headers):
            # Заголовки изменились — дропаем и пересоздаём
            with connection.schema_editor() as schema_editor:
                schema_editor.delete_model(DynamicModel)
            raise LookupError
        # Очищаем данные
        DynamicModel.objects.all().delete()
    except LookupError:
        # Создаём новую модель
        fields = {'__module__': f'{app_label}.models'}
        for col in headers:
            fields[col] = django_models.CharField(max_length=500, blank=True, null=True)
        DynamicModel = type(model_name, (django_models.Model,), fields)
        DynamicModel._meta.db_table = table_name
        apps.register_model(app_label, DynamicModel)
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(DynamicModel)

    # Вставляем новые данные
    for _, row in df.iterrows():
        data = {col: str(row[col]) if pd.notna(row[col]) else None for col in headers}
        DynamicModel.objects.create(**data)


def success(request, file_type):
    last_file = UploadedFile.objects.filter(type=file_type).order_by('-uploaded_at').first()
    return render(request, 'uploader/success.html', {
        'message': f'Файл для {file_type} успешно загружен и таблица обновлена!',
        'file_type': file_type,
        'uploaded_file': last_file
    })


def view_table(request, file_type):
    app_label = 'uploader'
    model_name = file_type.capitalize()
    try:
        DynamicModel = apps.get_model(app_label, model_name)
        rows = DynamicModel.objects.all()
        columns = [f.name for f in DynamicModel._meta.get_fields() if f.name != 'id']
        table_data = [[getattr(row, col, None) for col in columns] for row in rows]
    except LookupError:
        columns = []
        table_data = []

    return render(request, 'uploader/view_file.html', {
        'file_type': file_type,
        'columns': columns,
        'table_data': table_data
    })
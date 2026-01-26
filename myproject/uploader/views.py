import pandas as pd
from django.shortcuts import render, redirect
from .forms import UploadFileForm
from .models import UploadedFile, ImportedRow


def upload_file(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.save()
            process_excel_to_db(uploaded_file)
            return redirect('success')
    else:
        form = UploadFileForm()
    return render(request, 'uploader/upload.html', {'form': form})


def process_excel_to_db(uploaded_file):
    file_path = uploaded_file.file.path
    df = pd.read_excel(file_path)

    # Опционально: сохраняем заголовки (первую строку, если нужно)
    headers = df.columns.tolist()
    uploaded_file.headers = headers
    uploaded_file.save()

    # Импорт строк
    for i, row in df.iterrows():
        # Преобразуем NaN в None, и всё в str для безопасности (можно доработать типы)
        row_dict = {col: (None if pd.isna(val) else str(val)) for col, val in row.items()}
        ImportedRow.objects.create(
            file=uploaded_file,
            row_data=row_dict,
            row_number=i + 1  # 1-based
        )

def success(request):
    last_file = UploadedFile.objects.order_by('-uploaded_at').first()
    return render(request, 'uploader/success.html', {
        'message': 'Файл успешно загружен!',
        'uploaded_file': last_file
    })

def view_file(request, file_id):
    uploaded_file = UploadedFile.objects.get(id=file_id)
    rows = uploaded_file.rows.all()

    # Для рендеринга таблицы: собираем все уникальные колонки
    all_columns = set()
    for row in rows:
        all_columns.update(row.row_data.keys())
    columns = list(all_columns)  # Или используйте uploaded_file.headers, если сохранили

    # Данные для шаблона: список списков или dicts
    table_data = [[row.row_data.get(col) for col in columns] for row in rows]

    return render(request, 'uploader/view_file.html', {
        'file': uploaded_file,
        'columns': columns,
        'table_data': table_data
    })
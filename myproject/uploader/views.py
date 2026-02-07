# uploader/views.py
from datetime import datetime

from dateutil import parser
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
    table_name = f"uploader_{file_type}"

    try:
        DynamicModel = apps.get_model(app_label, model_name)
    except LookupError:
        # ... (ваш существующий код создания временной модели, если таблицы нет)
        # предполагаем, что он уже есть и работает
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                );
            """, [table_name])
            exists = cursor.fetchone()[0]

        if not exists:
            return render(request, 'uploader/view_file.html', {
                'file_type': file_type,
                'columns': [],
                'table_data': [],
                'months': None,
                'selected_month': '',
                'sections': [],
                'selected_section': '',
                'all_available_columns': [],
                'selected_columns': [],
                'row_count': 0,
            })

        # Получаем реальные колонки из БД
        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(cursor, table_name)
            all_fields = [field.name for field in description if field.name != 'id']

        # Создаём временную модель
        fields = {'__module__': f'{app_label}.models'}
        for col in all_fields:
            fields[col] = django_models.CharField(max_length=500, blank=True, null=True)
        DynamicModel = type(model_name, (django_models.Model,), fields)
        DynamicModel._meta.db_table = table_name
        apps.register_model(app_label, DynamicModel)

    # Все доступные поля
    all_available_columns = [
        f.name for f in DynamicModel._meta.get_fields()
        if f.name != 'id' and not f.name.startswith('_')
    ]
    all_available_columns.sort()  # для удобства

    # ──────────────────────────────────────────────
    # GET-параметры
    # ──────────────────────────────────────────────
    selected_month_str = request.GET.get('month', '').strip().lower()
    selected_section = request.GET.get('section', '').strip()
    default_cols = ['Заказ', 'ЗапланНачало', 'ПроизвУчасток']

    # Колонки — список из GET (может быть несколько значений)
    selected_columns_input = request.GET.getlist('columns')
    if selected_columns_input:
        selected_columns = default_cols + [c for c in selected_columns_input if c in all_available_columns]
    else:
        # По умолчанию — три основные, если существуют
        selected_columns = [c for c in default_cols if c in all_available_columns]

    # Если после фильтрации ничего не выбрано — берём все
    if not selected_columns:
        selected_columns = all_available_columns[:]

    # ──────────────────────────────────────────────
    # Фильтрация
    # ──────────────────────────────────────────────
    queryset = DynamicModel.objects.all()

    # Фильтр по участку
    if selected_section and 'ПроизвУчасток' in all_available_columns:
        queryset = queryset.filter(ПроизвУчасток=selected_section)

    # Фильтр по месяцу
    selected_month = None
    if file_type.lower() == 'plan' and selected_month_str:
        month_map = {
            'январь': 1, 'февраль': 2, 'март': 3, 'апрель': 4, 'май': 5, 'июнь': 6,
            'июль': 7, 'август': 8, 'сентябрь': 9, 'октябрь': 10, 'ноябрь': 11, 'декабрь': 12
        }
        month_num = month_map.get(selected_month_str)
        if month_num:
            selected_month = selected_month_str.capitalize()

    rows = list(queryset)  # или queryset.values(*selected_columns) для оптимизации

    # Подготовка данных для шаблона
    table_data = [
        [getattr(row, col, None) for col in selected_columns]
        for row in rows
    ]

    # Уникальные участки
    sections = []
    if 'ПроизвУчасток' in all_available_columns:
        sections = list(
            DynamicModel.objects
            .values_list('ПроизвУчасток', flat=True)
            .distinct()
            .exclude(ПроизвУчасток__isnull=True)
            .order_by('ПроизвУчасток')
        )

    months_list = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                   'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']

    context = {
        'file_type': file_type,
        'columns': selected_columns,
        'all_available_columns': all_available_columns,
        'selected_columns': selected_columns,
        'table_data': table_data,
        'months': months_list if file_type.lower() == 'plan' else None,
        'selected_month': selected_month,
        'sections': sections,
        'selected_section': selected_section,
        'row_count': len(table_data),
    }

    return render(request, 'uploader/view_file.html', context)
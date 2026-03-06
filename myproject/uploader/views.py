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
    source_table_name = f"uploader_{file_type}"

    # Получаем или создаём динамическую модель для исходной таблицы
    try:
        DynamicModel = apps.get_model(app_label, model_name)
    except LookupError:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                );
            """, [source_table_name])
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

        # Получаем колонки из БД
        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(cursor, source_table_name)
            all_fields = [field.name for field in description if field.name != 'id']

        fields = {'__module__': f'{app_label}.models'}
        for col in all_fields:
            fields[col] = django_models.CharField(max_length=500, blank=True, null=True)
        DynamicModel = type(model_name, (django_models.Model,), fields)
        DynamicModel._meta.db_table = source_table_name
        apps.register_model(app_label, DynamicModel)

    # Дефолтные колонки
    default_cols = ['Заказ', 'ЗапланНачало', 'ПроизвУчасток']

    # Все доступные колонки
    all_available_columns = sorted([
        f.name for f in DynamicModel._meta.get_fields()
        if f.name != 'id' and not f.name.startswith('_')
    ])

    columns_for_view = [value for value in all_available_columns if value not in default_cols]

    # GET-параметры
    selected_month_str = request.GET.get('month', '').strip().lower()
    selected_section = request.GET.get('section', '').strip()

    # Выбранные колонки из чекбоксов
    selected_columns_input = request.GET.getlist('columns')
    selected_columns = default_cols + [c for c in selected_columns_input if c in columns_for_view]

    # Если ничего не выбрано → используем дефолтные три (или все, если дефолтных нет)
    if not selected_columns:
        selected_columns = default_cols if default_cols else columns_for_view

    # Фильтрация
    queryset = DynamicModel.objects.all()

    # Фильтр по участку
    if selected_section and 'ПроизвУчасток' in all_available_columns:
        queryset = queryset.filter(ПроизвУчасток=selected_section)

    # Фильтр по месяцу (пример с LIKE, адаптируйте под ваш формат дат)
    selected_month = None
    month_filter_sql = ''
    month_params = []
    if file_type.lower() == 'plan' and selected_month_str:
        month_map = {
            'январь':1, 'февраль':2, 'март':3, 'апрель':4, 'май':5, 'июнь':6,
            'июль':7, 'август':8, 'сентябрь':9, 'октябрь':10, 'ноябрь':11, 'декабрь':12
        }
        month_num = month_map.get(selected_month_str)
        if month_num:
            selected_month = selected_month_str.capitalize()
            month_str = f'{month_num:02d}'
            date_fields = ['БазисСрокНачала', 'БазисСрокКонца', 'ЗапланНачало']  # добавьте нужные
            #date_fields = [f for f in date_fields if f in all_available_columns]
            if date_fields:
                month_filter_parts = [f'"{f}" LIKE %s' for f in date_fields]
                month_filter_sql = ' OR '.join(month_filter_parts)
                month_filter_sql = f'AND ({month_filter_sql})' if month_filter_parts else ''
                month_params = [f'%-{month_str}-%'] * len(date_fields)

    # Получаем отфильтрованные строки
    if month_filter_sql or selected_section:
        with connection.cursor() as cursor:
            query = f'SELECT * FROM {source_table_name} WHERE 1=1'
            params = []
            if selected_section:
                query += ' AND "ПроизвУчасток" = %s'
                params.append(selected_section)
            if month_filter_sql:
                query += f' {month_filter_sql}'
                params.extend(month_params)
            cursor.execute(query, params)
            rows = [DynamicModel(**dict(zip([f.name for f in DynamicModel._meta.get_fields()], row)))
                    for row in cursor.fetchall()]
    else:
        rows = list(queryset)

    # Данные для отображения (только выбранные колонки)
    table_data = [
        [getattr(row, col, None) for col in selected_columns]
        for row in rows
    ]

    # Сохранение отфильтрованной таблицы (только выбранные колонки!)
    filtered_table_name = 'uploader_filtered_plan'
    saved_message = None

    has_filters = bool(selected_month_str or selected_section)
    if has_filters and selected_columns:
        with connection.cursor() as cursor:
            # 1. Создаём новую таблицу с нужными колонками
            columns_def = ', '.join([f'"{col}" TEXT' for col in selected_columns])
            cursor.execute(f"""
                DROP TABLE IF EXISTS {filtered_table_name};
                CREATE TABLE {filtered_table_name} (
                    id SERIAL PRIMARY KEY,
                    {columns_def}
                );
            """)

            # 2. Вставляем только выбранные колонки
            columns_list = ', '.join([f'"{col}"' for col in selected_columns])
            select_list = ', '.join([f'"{col}"' for col in selected_columns])
            insert_query = f"""
                INSERT INTO {filtered_table_name} ({columns_list})
                SELECT {select_list}
                FROM {source_table_name}
                WHERE 1=1
            """
            insert_params = []
            if selected_section:
                insert_query += ' AND "ПроизвУчасток" = %s'
                insert_params.append(selected_section)
            if month_filter_sql:
                insert_query += f' {month_filter_sql}'
                insert_params.extend(month_params)

            cursor.execute(insert_query, insert_params)

        saved_message = f'Отфильтрованная таблица сохранена в {filtered_table_name} (только выбранные колонки).'

    # Уникальные участки для выпадающего списка
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
        'columns_for_view': columns_for_view,
        'selected_columns': selected_columns,
        'table_data': table_data,
        'months': months_list if file_type.lower() == 'plan' else None,
        'selected_month': selected_month,
        'sections': sections,
        'selected_section': selected_section,
        'row_count': len(table_data),
        'saved_message': saved_message,
        'selected_month_lower': selected_month_str,
    }

    return render(request, 'uploader/view_file.html', context)
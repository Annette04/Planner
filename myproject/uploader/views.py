from django.db import connection, models as django_models
from django.apps import apps
import pandas as pd
from django.db import connection
from django.shortcuts import render, redirect
from .forms import UploadForm
from .models import UploadedFile
from .services import get_dynamic_model, build_month_filter, save_filtered_plan_table


def home(request):
    return render(request, 'uploader/home.html')


def upload(request, file_type):
    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            uploaded_file = UploadedFile.objects.create(type=file_type, file=file)
            process_excel_to_db(uploaded_file, file_type)
            return redirect('success', file_type=file_type)
    else:
        form = UploadForm()
    return render(request, 'uploader/upload.html', {'form': form, 'file_type': file_type})


def process_excel_to_db(uploaded_file, file_type):
    #Создаёт таблицу при первой загрузке + обновляет при изменении заголовков
    file_path = uploaded_file.file.path
    df = pd.read_excel(file_path)
    headers = df.columns.tolist()
    uploaded_file.headers = headers
    uploaded_file.save()

    app_label = 'uploader'
    model_name = file_type.capitalize()
    table_name = f"uploader_{file_type}"

    # Пытаемся получить модель
    try:
        DynamicModel = get_dynamic_model(file_type)
        existing_fields = [f.name for f in DynamicModel._meta.get_fields() if f.name != 'id']
        if sorted(existing_fields) != sorted(headers):
            raise LookupError("Структура изменилась")
        DynamicModel.objects.all().delete()
    except (ValueError, LookupError):
        # Таблицы нет или структура изменилась → создаём новую
        with connection.cursor() as cursor:
            columns_def = ', '.join([f'"{col}" TEXT' for col in headers])
            cursor.execute(f"""
                DROP TABLE IF EXISTS "{table_name}" CASCADE;
                CREATE TABLE "{table_name}" (
                    id SERIAL PRIMARY KEY,
                    {columns_def}
                );
            """)

        # Создаём модель
        fields = {'__module__': f'{app_label}.models'}
        for col in headers:
            fields[col] = django_models.CharField(max_length=500, blank=True, null=True)
        DynamicModel = type(model_name, (django_models.Model,), fields)
        DynamicModel._meta.db_table = table_name
        apps.register_model(app_label, DynamicModel)

    # Заполняем данными
    for _, row in df.iterrows():
        data = {}
        for col in headers:
            val = row[col]
            if pd.isna(val):
                data[col] = None
            elif isinstance(val, (int, float)):
                # Если число целое — сохраняем как int, иначе как float → str
                if val == int(val):
                    data[col] = str(int(val))
                else:
                    data[col] = str(val)
            else:
                data[col] = str(val)
        DynamicModel.objects.create(**data)


def success(request, file_type):
    last_file = UploadedFile.objects.filter(type=file_type).order_by('-uploaded_at').first()
    return render(request, 'uploader/success.html', {
        'message': f'Файл для {file_type} успешно загружен!',
        'file_type': file_type,
        'uploaded_file': last_file
    })


def view_table(request, file_type):
    DynamicModel = get_dynamic_model(file_type)
    source_table_name = f"uploader_{file_type}"

    all_available_columns = sorted([
        f.name for f in DynamicModel._meta.get_fields()
        if f.name != 'id' and not f.name.startswith('_')
    ])

    # Логика отображения и фильтров — разная для 'plan'
    is_plan = file_type.lower() == 'plan'

    if is_plan:
        # Только для plan: дефолтные колонки + чекбоксы остальных
        default_cols = ['Заказ', 'ЗапланНачало', 'ПроизвУчасток']
        columns_for_view = [col for col in all_available_columns if col not in default_cols]

        selected_month_str = request.GET.get('month', '').strip().lower()
        selected_section = request.GET.get('section', '').strip()
        selected_columns_input = request.GET.getlist('columns')

        selected_columns = default_cols + [c for c in selected_columns_input if c in columns_for_view]
        if not selected_columns:
            selected_columns = default_cols if default_cols else all_available_columns

        # Фильтрация только для plan
        queryset = DynamicModel.objects.all()
        if selected_section and 'ПроизвУчасток' in all_available_columns:
            queryset = queryset.filter(ПроизвУчасток=selected_section)

        date_fields = ['БазисСрокНачала', 'БазисСрокКонца', 'ЗапланНачало']
        month_condition, month_params = build_month_filter(selected_month_str, date_fields)

        if month_condition or selected_section:
            with connection.cursor() as cursor:
                query = f'SELECT * FROM "{source_table_name}" WHERE 1=1'
                params = []
                if selected_section:
                    query += ' AND "ПроизвУчасток" = %s'
                    params.append(selected_section)
                if month_condition:
                    query += month_condition
                    params.extend(month_params)
                cursor.execute(query, params)
                rows = [DynamicModel(**dict(zip([f.name for f in DynamicModel._meta.get_fields()], row)))
                        for row in cursor.fetchall()]
        else:
            rows = list(queryset)

        # Сохранение отфильтрованной таблицы — только для plan
        saved_message = None
        if (selected_month_str or selected_section) and selected_columns:
            save_filtered_plan_table(selected_columns, selected_section, month_condition, month_params, source_table_name)
            saved_message = f'Таблица uploader_filtered_plan обновлена ({len(table_data)} строк)'
    else:
        # Для всех остальных типов — показываем все колонки без фильтров
        selected_columns = all_available_columns
        selected_month_str = ''
        selected_section = ''
        selected_month_lower = ''
        rows = list(DynamicModel.objects.all())
        saved_message = None
        columns_for_view = []  # не показываем чекбоксы

    # Общее для всех
    table_data = [[getattr(row, col, None) for col in selected_columns] for row in rows]

    sections = []
    if is_plan and 'ПроизвУчасток' in all_available_columns:
        sections = list(DynamicModel.objects
                        .values_list('ПроизвУчасток', flat=True)
                        .distinct()
                        .exclude(ПроизвУчасток__isnull=True)
                        .order_by('ПроизвУчасток'))

    months_list = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                   'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']

    context = {
        'file_type': file_type,
        'columns': selected_columns,
        'columns_for_view': columns_for_view if is_plan else [],
        'selected_columns': selected_columns,
        'table_data': table_data,
        'months': months_list if is_plan else None,
        'selected_month': selected_month_str.capitalize() if selected_month_str else None,
        'selected_month_lower': selected_month_str if is_plan else '',
        'sections': sections,
        'selected_section': selected_section,
        'row_count': len(table_data),
        'saved_message': saved_message,
    }

    return render(request, 'uploader/view_file.html', context)
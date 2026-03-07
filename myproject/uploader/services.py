from django.db import connection, models as django_models
from django.apps import apps


def get_dynamic_model(file_type: str):
    #Возвращает динамическую модель ТОЛЬКО если таблица уже существует
    app_label = 'uploader'
    model_name = file_type.capitalize()
    table_name = f"uploader_{file_type}"

    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
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
            raise ValueError(f"Таблица {table_name} не найдена. Сначала загрузите файл.")

        # Получаем колонки из БД
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
        return DynamicModel


def build_month_filter(selected_month_str: str, date_fields: list):
    #Возвращает SQL-условие и параметры для фильтра по месяцу
    if not selected_month_str:
        return '', []

    month_map = {
        'январь':1, 'февраль':2, 'март':3, 'апрель':4, 'май':5, 'июнь':6,
        'июль':7, 'август':8, 'сентябрь':9, 'октябрь':10, 'ноябрь':11, 'декабрь':12
    }
    month_num = month_map.get(selected_month_str)
    if not month_num:
        return '', []

    month_str = f'{month_num:02d}'
    parts = [f'"{f}" LIKE %s' for f in date_fields]
    condition = f'AND ({" OR ".join(parts)})' if parts else ''
    params = [f'%-{month_str}-%'] * len(parts)
    return condition, params


def save_filtered_plan_table(selected_columns, selected_section, month_condition, month_params, source_table_name):
    #Создаёт/обновляет таблицу uploader_filtered_plan (только выбранные колонки)
    filtered_table_name = 'uploader_filtered_plan'

    with connection.cursor() as cursor:
        cursor.execute(f'DROP TABLE IF EXISTS "{filtered_table_name}"')

        columns_def = ', '.join([f'"{col}" TEXT' for col in selected_columns])
        cursor.execute(f"""
            CREATE TABLE "{filtered_table_name}" (
                id SERIAL PRIMARY KEY,
                {columns_def}
            );
        """)

        columns_list = ', '.join([f'"{col}"' for col in selected_columns])
        insert_query = f"""
            INSERT INTO "{filtered_table_name}" ({columns_list})
            SELECT {columns_list}
            FROM "{source_table_name}"
            WHERE 1=1
        """
        insert_params = []
        if selected_section:
            insert_query += ' AND "ПроизвУчасток" = %s'
            insert_params.append(selected_section)
        if month_condition:
            insert_query += f' {month_condition}'
            insert_params.extend(month_params)

        cursor.execute(insert_query, insert_params)


def get_materials_by_order(order_number: str):
    """Возвращает все материалы для конкретного заказа"""
    try:
        MaterialsModel = get_dynamic_model('materials_in_order')

        # Ищем по полю "Заказ" (точное совпадение)
        materials = MaterialsModel.objects.filter(Заказ=order_number)

        result = []
        for item in materials:
            row = {}
            for field in MaterialsModel._meta.get_fields():
                if field.name != 'id':
                    row[field.name] = getattr(item, field.name, None)
            result.append(row)
        return result
    except Exception:
        return []  # если таблицы ещё нет или ошибка
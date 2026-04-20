from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('upload/<str:file_type>/', views.upload, name='upload'),
    path('success/<str:file_type>/', views.success, name='success'),
    path('view/<str:file_type>/', views.view_table, name='view_table'),
    path('materials/<str:order_number>/', views.get_materials_for_order, name='get_materials_for_order'),
    path('download/<str:file_type>/', views.download_table_excel, name='download_table'),
]
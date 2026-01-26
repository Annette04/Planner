from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('upload/<str:file_type>/', views.upload, name='upload'),
    path('success/<str:file_type>/', views.success, name='success'),
    path('view/<str:file_type>/', views.view_table, name='view_table'),
]
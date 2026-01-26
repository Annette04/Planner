from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_file, name='upload_file'),
    path('success/', views.success, name='success'),
    path('view/<int:file_id>/', views.view_file, name='view_file'),
]
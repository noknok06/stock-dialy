# analysis_templates/urls.py
from django.urls import path
from . import views

app_name = 'analysis_templates'

urlpatterns = [
    # テンプレート管理
    path('templates/', views.AnalysisTemplateListView.as_view(), name='list'),
    path('templates/create/', views.AnalysisTemplateCreateView.as_view(), name='create'),
    path('templates/<int:pk>/', views.AnalysisTemplateDetailView.as_view(), name='detail'),
    path('templates/<int:pk>/edit/', views.AnalysisTemplateUpdateView.as_view(), name='update'),
    path('templates/<int:pk>/delete/', views.AnalysisTemplateDeleteView.as_view(), name='delete'),
    
    # 日記分析データ入力
    path('diary/<int:diary_id>/analysis/', views.StockAnalysisDataInputView.as_view(), name='data_input'),
    
    # AJAX API
    path('api/save-analysis-data/', views.save_analysis_data, name='save_analysis_data'),
    path('api/get-template-fields/<int:template_id>/', views.get_template_fields, name='get_template_fields'),
    path('api/get-analysis-data/<int:diary_id>/<int:template_id>/', views.get_analysis_data, name='get_analysis_data'),
    
    # 比較機能
    path('comparison/', views.AnalysisComparisonView.as_view(), name='comparison'),
]
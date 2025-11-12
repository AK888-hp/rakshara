from django.urls import path
from . import views

urlpatterns = [
    # --- THIS LINE IS REMOVED to prevent an infinite loop ---
    # path('', views.teacher_dashboard, name='teacher_dashboard'),

    # Classroom views
    path('classroom/<int:pk>/', views.classroom_detail, name='classroom_detail'),
    path('classroom/<int:pk>/quick-check/', views.quick_checkup, name='quick_checkup'),
    
    # Request handling
    path('approve/<int:req_id>/', views.approve_request, name='approve_request'),
    path('reject/<int:req_id>/', views.reject_request, name='reject_request'),

    # Student handling
    path('student/<int:student_id>/remove-from-class/<int:class_id>/', 
         views.delete_student_from_class, 
         name='delete_student_from_class'),

    path('student/<int:student_id>/history/', 
         views.view_student_history, 
         name='view_student_history'),
         
    path('classroom/<int:pk>/delete/', 
         views.delete_classroom, 
         name='delete_classroom'),
]
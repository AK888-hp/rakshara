from django.urls import path
from . import views

urlpatterns = [
    path('register/student/', views.student_register, name='student_register'),
    path('register/teacher/', views.teacher_register, name='teacher_register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('verify-signup-otp/', views.verify_teacher_signup_otp, name='verify_teacher_signup_otp'),
    path('verify-login-otp/', views.verify_teacher_login_otp, name='verify_teacher_login_otp'),

]

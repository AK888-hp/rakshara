from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  # ✅ Home page route
    path('register/student/', views.student_register, name='student_register'),
    path('register/teacher/', views.teacher_register, name='teacher_register'),
    path('login/', views.login_view, name='login'),
    path('accounts/logout/', views.logout_view, name='logout'),
    # OTP Verification URLs (FIXED NAMES)
    path('verify/teacher/signup/', views.verify_teacher_signup_otp, name='verify_teacher_signup_otp'), # <-- CHANGED
    path('verify/teacher/login/', views.verify_teacher_login_otp, name='verify_teacher_login_otp'), # <-- CHANGED
    path('set-language/', views.set_language, name='set_language'),
    # New URLs for placeholder pages
    path('settings/', views.settings_page, name='settings'),
    path('help/', views.help_center_page, name='help_center'),
    path('faq/', views.faq_page, name='faq'),
    path('profile/', views.student_profile, name='student_profile'),
    path('profile/edit/', views.edit_student_profile, name='edit_student_profile'),
    path('profile/student/<str:student_code>/', views.teacher_view_student_profile, name='teacher_view_student_profile'),

]

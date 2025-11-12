from django.contrib import admin
from django.urls import path, include
from accounts.views import set_language
from django.conf import settings               # <-- 1. IMPORT
from django.conf.urls.static import static     # <-- 2. IMPORT

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),  # ✅ this ensures '/' goes to home()
    path('classroom/', include('classroom.urls')),
    path('health/', include('health.urls')),
    path('set-language/', set_language, name='set_language'),
]
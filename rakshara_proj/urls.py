from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # This includes login, register, home, etc.
    path('', include('accounts.urls')), 
    
    # This line is FIXED to include the 'health' namespace
    path('health/', include(('health.urls', 'health'), namespace='health')),
    
    # This includes classroom_detail, approve, reject, etc.
    path('classroom/', include('classroom.urls')),
]
"""
Django settings for rakshara_proj project.
"""

from pathlib import Path
import os  # <-- 1. IMPORT OS
import dj_database_url # <-- 2. IMPORT dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# 3. USE ENVIRONMENT VARIABLES FOR ALL SECRETS
# This is NOT your secret key, it's a fallback for local development
SECRET_KEY = os.environ.get(
    'SECRET_KEY', 
    'django-insecure-y3g^-v1ixckrquz002=#$gp+n!4^1&=nh!*0_7qg!tln!-@38s'
)

# 4. DEBUG MUST BE 'False' IN PRODUCTION
# Render will set 'RENDER' to 'true'.
DEBUG = 'RENDER' not in os.environ

# 5. CONFIGURE ALLOWED_HOSTS
ALLOWED_HOSTS = ['rakshara-web.onrender.com']
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_URL')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# This is for local testing (won't be used on Render)
if not 'RENDER' in os.environ:
    ALLOWED_HOSTS.append('127.0.0.1')
    ALLOWED_HOSTS.append('localhost')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    # 6. ADD WHITENOISE
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'accounts',
    'health',
    'classroom',
    'ai_engine',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # 7. ADD WHITENOISE MIDDLEWARE (RIGHT AFTER SECURITY)
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware', 
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'rakshara_proj.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'rakshara_proj.wsgi.application'


# 8. CONFIGURE PRODUCTION DATABASE (PostgreSQL)
# This will read the DATABASE_URL from Render's environment
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600
    )
}


# Password validation
# ... (this section is unchanged)
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
# ... (this section is unchanged)
USE_I18N = True
LANGUAGE_CODE = 'en-us'
LANGUAGES = [('en', 'English'), ('kn', 'Kannada'), ('hi', 'Hindi')]
LOCALE_PATHS = [BASE_DIR / 'locale']
TIME_ZONE = 'UTC'
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# 9. CONFIGURE STATIC FILES FOR PRODUCTION
STATIC_URL = '/static_images/'
STATICFILES_DIRS = [
    BASE_DIR / 'static_images',
]
# This is the folder WhiteNoise will find all your files in
STATIC_ROOT = BASE_DIR / 'staticfiles'
# This makes WhiteNoise more efficient
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Media files (User Uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'accounts.User'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'
LOGIN_URL = 'login'

# 10. USE ENVIRONMENT VARIABLES FOR EMAIL
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.environ.get('EMAIL_HOST_USER')
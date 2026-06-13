import os
import environ
import dj_database_url
from celery.schedules import crontab
from pathlib import Path

# ── 1. INITIALIZE ENVIRONMENT VARIABLES ──────────────────────────────────────
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
# Take environment variables from .env file
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# ── 2. SECURITY WARNINGS ─────────────────────────────────────────────────────
# সিক্রেট কী এবং ডিবগ মোড .env থেকে নেবে, না পেলে ডিফল্টটা ব্যবহার করবে
SECRET_KEY = env('SECRET_KEY', default='django-insecure-7d%(%-z$9!_9b-3ls3#xk5ll@zwd@!ygb6#^u=2aeq^c5y_wwi')
DEBUG = env.bool('DEBUG', default=True) 

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*'] # Render এবং Localhost সবকিছুর জন্য পারমিশন
CSRF_TRUSTED_ORIGINS = ['http://localhost:8080', 'http://127.0.0.1:8080']

# ── 3. APPLICATION DEFINITION ────────────────────────────────────────────────
INSTALLED_APPS =[
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'rest_framework',
    'django_filters',
    'myapp',
    'odoo_sync.apps.OdooSyncConfig',
]

MIDDLEWARE =[
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # 🟢 Render-এ CSS পাওয়ার জন্য এটি মাস্ট!
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'upcycle.urls'

TEMPLATES =[
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS':[os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors':[
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'upcycle.wsgi.application'
ASGI_APPLICATION = 'upcycle.asgi.application'

# ── 4. DATABASE & AUTH ───────────────────────────────────────────────────────
DATABASES = {
    'default': env.db('DATABASE_URL', default=f"sqlite:///{os.path.join(BASE_DIR, 'db.sqlite3')}")
}

AUTH_USER_MODEL = 'myapp.CustomUser'

AUTH_PASSWORD_VALIDATORS =[
    # ... (default validators can go here)
]

# ── 5. INTERNATIONALIZATION ──────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ── 6. STATIC & MEDIA FILES (🟢 FIXED E002 ERROR) ────────────────────────────
STATIC_URL = '/static/'

# প্রোডাকশনে (Render-এ) জ্যাঙ্গো সব স্ট্যাটিক ফাইল এই 'staticfiles' ফোল্ডারে জমা করবে
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# আপনার নিজের তৈরি করা CSS/JS গুলো এই 'static' ফোল্ডারে থাকবে
STATICFILES_DIRS =[
    os.path.join(BASE_DIR, 'static'), 
]

# WhiteNoise storage - স্ট্যাটিক ফাইল ফাস্ট লোড করার জন্য
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ── 7. OTHER SETTINGS ────────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_REDIRECT_URL = '/home/'
LOGOUT_REDIRECT_URL = '/'

# ── 8. STRIPE & API KEYS ─────────────────────────────────────────────────────
STRIPE_PUBLIC_KEY = env('STRIPE_PUBLIC_KEY', default='')
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY', default='')

# ── 9. ODOO XML-RPC SETTINGS ────────────────────────────────────────────────
ODOO_URL = env('ODOO_URL', default='')
ODOO_DB = env('ODOO_DB', default='')
ODOO_USERNAME = env('ODOO_USERNAME', default='')
ODOO_PASSWORD = env('ODOO_PASSWORD', default='')

# ── 10. CELERY BEAT SCHEDULE ────────────────────────────────────────────────
CELERY_BEAT_SCHEDULE = {
    'sync_odoo_delta': {
        'task': 'odoo_sync.tasks.sync_odoo_products_delta',
        'schedule': 30 * 60,
        'kwargs': {'triggered_by': 'celery-beat'},
    },
    'sync_odoo_full': {
        'task': 'odoo_sync.tasks.sync_odoo_products_full',
        'schedule': crontab(hour=3, minute=0),
        'kwargs': {'triggered_by': 'celery-beat'},
    },
}

# ── 11. DJANGO REST FRAMEWORK ───────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'EXCEPTION_HANDLER': 'odoo_sync.exceptions.problem_detail_exception_handler',
}

# ── 12. DJANGO CHANNELS ─────────────────────────────────────────────────────
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [env('REDIS_URL', default='redis://127.0.0.1:6379/0')],
        },
    },
}

# ── CELERY BROKER ────────────────────────────────────────────────────────────
CELERY_BROKER_URL = env('REDIS_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND = env('REDIS_URL', default='redis://redis:6379/0')

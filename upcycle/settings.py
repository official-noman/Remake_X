import os
import environ
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

ALLOWED_HOSTS = ['*'] # Render এবং Localhost সবকিছুর জন্য পারমিশন

# ── 3. APPLICATION DEFINITION ────────────────────────────────────────────────
INSTALLED_APPS =[
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'myapp',
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

# ── 4. DATABASE & AUTH ───────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
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
from pathlib import Path
from dotenv import load_dotenv
import os
import mongoengine

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-this-in-production')

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'accounts',
    'academics',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'edusphere.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR.parent / 'frontend'],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.request',
        ],
    },
}]

WSGI_APPLICATION = 'edusphere.wsgi.application'

# No SQL database — using MongoDB via mongoengine
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.dummy',
    }
}

MONGODB_URI = os.environ.get('MONGODB_URI')
if not MONGODB_URI:
    raise RuntimeError(f'MONGODB_URI is missing; configure it in {BASE_DIR / ".env"}')

# Atlas SRV connections use TLS by default; tls=True makes that requirement
# explicit. Certificate and hostname verification remain enabled by PyMongo.
mongoengine.connect(
    db=os.environ.get('DB_NAME', 'edusphere_db'),
    host=MONGODB_URI,
    tls=True,
    serverSelectionTimeoutMS=8000,
    connectTimeoutMS=8000,
    socketTimeoutMS=20000,
    appName='EduSphereAI',
)

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'uploads'

# Temporary quiz syllabus uploads are limited server-side; configure in bytes.
try:
    QUIZ_SYLLABUS_MAX_FILE_SIZE = int(os.environ.get('QUIZ_SYLLABUS_MAX_FILE_SIZE', str(10 * 1024 * 1024)))
except ValueError:
    QUIZ_SYLLABUS_MAX_FILE_SIZE = 10 * 1024 * 1024
if QUIZ_SYLLABUS_MAX_FILE_SIZE < 1:
    QUIZ_SYLLABUS_MAX_FILE_SIZE = 10 * 1024 * 1024

# AI quiz generation is intentionally disabled while the local integration is under development.
QUIZ_AI_GENERATION_ENABLED = False

# DRF
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'accounts.authentication.MongoJWTAuthentication',
    ),
    'EXCEPTION_HANDLER': 'accounts.exceptions.mongo_exception_handler',
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'UNAUTHENTICATED_USER': None,
    'UNAUTHENTICATED_TOKEN': None,
}

# CORS — allow frontend dev server
CORS_ALLOW_ALL_ORIGINS = True

# Google OAuth
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')

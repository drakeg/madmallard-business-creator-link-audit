import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get('SECRET_KEY', 'tests-only-do-not-use')
DEBUG = False
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
INSTALLED_APPS = ['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','audit']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','audit.youtube_views.YouTubeRetentionMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[], 'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
DATABASES = {'default':{'ENGINE':'django.db.backends.sqlite3','NAME':os.getenv('DB_PATH',str(BASE_DIR/'db.sqlite3')),'OPTIONS':{'timeout':30}}}
AUTH_PASSWORD_VALIDATORS = [{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':12}},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}]
USE_TZ=True
TIME_ZONE='UTC'
STATIC_URL='/static/'
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
LOGIN_URL='/login/'
LOGIN_REDIRECT_URL='/'
PASSWORD_RESET_TIMEOUT=3600  # Admin-issued links expire after one hour.
LOGOUT_REDIRECT_URL='/login/'
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE='Lax'
SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','false')=='true'
CSRF_COOKIE_SECURE=SESSION_COOKIE_SECURE
SECURE_CONTENT_TYPE_NOSNIFF=True
SECURE_REFERRER_POLICY='same-origin'
X_FRAME_OPTIONS='DENY'
DATA_UPLOAD_MAX_MEMORY_SIZE=2_000_000
FILE_UPLOAD_MAX_MEMORY_SIZE=1_000_000
SCAN_CONCURRENCY=max(1,min(10,int(os.getenv('SCAN_CONCURRENCY','4'))))
SCAN_TIMEOUT=max(2,min(30,int(os.getenv('SCAN_TIMEOUT','10'))))
SCAN_RETRIES=max(0,min(3,int(os.getenv('SCAN_RETRIES','1'))))
MAX_SOURCES=max(1,min(20,int(os.getenv('MAX_SOURCES','20'))))
MAX_LINKS=max(1,min(100,int(os.getenv('MAX_LINKS','100'))))
LYCHEE_BIN=os.getenv('LYCHEE_BIN','lychee')

YOUTUBE_API_KEY=os.getenv("YOUTUBE_API_KEY", "")

# Keep server errors diagnosable with DEBUG disabled. Never log POST bodies/keys.
LOGGING={
    'version':1,'disable_existing_loggers':False,
    'handlers':{'app_console':{'class':'logging.StreamHandler'}},
    'loggers':{
        'audit':{'handlers':['app_console'],'level':'INFO','propagate':False},
        'django.request':{'handlers':['app_console'],'level':'ERROR','propagate':False},
    },
}

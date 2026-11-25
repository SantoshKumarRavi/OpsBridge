import json,os
from pathlib import Path
BASE_DIR=Path(__file__).resolve().parent.parent
SECRET_KEY=os.getenv('DJANGO_SECRET_KEY','local-only-change-before-deploy')
DEBUG=os.getenv('APP_ENV','development')!='production'
ALLOWED_HOSTS=os.getenv('DJANGO_ALLOWED_HOSTS','*').split(',')
INSTALLED_APPS=['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','rest_framework','corsheaders','onboarding']
MIDDLEWARE=['onboarding.middleware.CorrelationIdMiddleware','django.middleware.security.SecurityMiddleware','corsheaders.middleware.CorsMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF='config.urls'; TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION='config.wsgi.application'; ASGI_APPLICATION='config.asgi.application'
database_secret={}
if os.getenv('POSTGRES_MASTER_SECRET_JSON'):
 database_secret=json.loads(os.environ['POSTGRES_MASTER_SECRET_JSON'])
DATABASES={'default':{'ENGINE':'django.db.backends.postgresql','NAME':os.getenv('POSTGRES_DB',database_secret.get('dbname','opsbridge')),'USER':database_secret.get('username',os.getenv('POSTGRES_USER','opsbridge')),'PASSWORD':database_secret.get('password',os.getenv('POSTGRES_PASSWORD','opsbridge')),'HOST':database_secret.get('host',os.getenv('POSTGRES_HOST','localhost')),'PORT':database_secret.get('port',os.getenv('POSTGRES_PORT','5432')),'CONN_MAX_AGE':60,'OPTIONS':{'connect_timeout':5,'sslmode':'require' if os.getenv('APP_ENV')=='production' else 'prefer'}}}
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'; STATIC_URL='static/'; MEDIA_ROOT=os.getenv('MEDIA_ROOT',str(BASE_DIR/'uploads')); MEDIA_URL='/media/'
DATA_UPLOAD_MAX_MEMORY_SIZE=16*1024*1024; FILE_UPLOAD_MAX_MEMORY_SIZE=4*1024*1024
REST_FRAMEWORK={'DEFAULT_AUTHENTICATION_CLASSES':[],'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.AllowAny'],'DEFAULT_RENDERER_CLASSES':['rest_framework.renderers.JSONRenderer'],'DEFAULT_THROTTLE_CLASSES':['rest_framework.throttling.AnonRateThrottle'],'DEFAULT_THROTTLE_RATES':{'anon':'300/hour'}}
CELERY_BROKER_URL=os.getenv('RABBITMQ_URL','amqp://opsbridge:opsbridge@localhost:5672/'); CELERY_RESULT_BACKEND=os.getenv('REDIS_URL','redis://localhost:6379/1'); CELERY_TASK_ACKS_LATE=True; CELERY_TASK_REJECT_ON_WORKER_LOST=True; CELERY_TASK_SERIALIZER='json'; CELERY_ACCEPT_CONTENT=['json']; CELERY_TASK_TIME_LIMIT=900; CELERY_BEAT_SCHEDULE={'publish-opsbridge-outbox':{'task':'onboarding.tasks.publish_pending_events','schedule':3.0}}
USE_S3=os.getenv('USE_S3','false').lower()=='true'
STORAGES={'default':{'BACKEND':'storages.backends.s3boto3.S3Boto3Storage' if USE_S3 else 'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}}
if USE_S3:
 AWS_STORAGE_BUCKET_NAME=os.environ['S3_BUCKET']; AWS_S3_REGION_NAME=os.getenv('AWS_REGION','ap-south-1'); AWS_S3_ENDPOINT_URL=os.getenv('AWS_ENDPOINT_URL') or None; AWS_DEFAULT_ACL=None; AWS_S3_FILE_OVERWRITE=False; AWS_S3_OBJECT_PARAMETERS={'CacheControl':'max-age=86400'}

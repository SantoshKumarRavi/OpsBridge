from rest_framework import serializers
from django.utils import timezone
from .models import OnboardingCase,CaseDocument,AuditEvent,VoiceContact
class CaseCreateSerializer(serializers.ModelSerializer):
 workerName=serializers.CharField(source='worker_name',max_length=180)
 class Meta: model=OnboardingCase; fields=['workerName','email','phone','role','country']
 def validate_country(self,value):
  if len(value)!=2: raise serializers.ValidationError('Country must be an ISO 3166-1 alpha-2 code.')
  return value.upper()
class DocumentSerializer(serializers.ModelSerializer):
 class Meta: model=CaseDocument; fields=['id','document_type','original_name','mime_type','size_bytes','status','confidence','extracted_fields','warnings','created_at']
class AuditSerializer(serializers.ModelSerializer):
 class Meta: model=AuditEvent; fields=['id','actor_id','event_type','details','correlation_id','created_at']
class CaseSerializer(serializers.ModelSerializer):
 documents=DocumentSerializer(many=True,read_only=True); audit_events=AuditSerializer(many=True,read_only=True)
 class Meta: model=OnboardingCase; fields=['id','tenant_id','worker_name','email','phone','role','country','status','extraction','ai_recommendation','assigned_to','decision_reason','version','created_at','updated_at','documents','audit_events']

class VoiceContactUpdateSerializer(serializers.Serializer):
 phoneNumber=serializers.RegexField(r'^\+[1-9][0-9]{6,14}$',max_length=16)
 consentStatus=serializers.ChoiceField(source='consent_status',choices=['unknown','granted','revoked'])
 consentRecordedAt=serializers.DateTimeField(source='consent_recorded_at',required=False,allow_null=True)
 consentSource=serializers.CharField(source='consent_source',max_length=120,required=False,allow_blank=True)
 consentReference=serializers.CharField(source='consent_reference',max_length=255,required=False,allow_blank=True)
 suppressed=serializers.BooleanField()
 suppressionReason=serializers.CharField(source='suppression_reason',max_length=255,required=False,allow_blank=True)
 def validate(self,attrs):
  if attrs.get('consent_status')=='granted' and (not attrs.get('consent_recorded_at') or not attrs.get('consent_source','').strip()):
   raise serializers.ValidationError('Granted consent requires a recording timestamp and source.')
  recorded_at=attrs.get('consent_recorded_at')
  if recorded_at and recorded_at>timezone.now():
   raise serializers.ValidationError({'consentRecordedAt':'Consent timestamp cannot be in the future.'})
  if attrs.get('suppressed') and not attrs.get('suppression_reason','').strip():
   raise serializers.ValidationError({'suppressionReason':'A reason is required when suppressing a number.'})
  return attrs

import uuid
from django.db import models

class TenantOwned(models.Model):
 tenant_id=models.CharField(max_length=100,db_index=True)
 created_at=models.DateTimeField(auto_now_add=True)
 updated_at=models.DateTimeField(auto_now=True)
 class Meta: abstract=True

class OnboardingCase(TenantOwned):
 STATUS=[('submitted','Submitted'),('processing','Processing'),('review_required','Needs review'),('ready','Ready to approve'),('approved','Approved'),('rejected','Rejected'),('changes_requested','Changes requested')]
 id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
 worker_name=models.CharField(max_length=180); email=models.EmailField(); phone=models.CharField(max_length=32,blank=True); role=models.CharField(max_length=160,blank=True); country=models.CharField(max_length=2,default='IN')
 status=models.CharField(max_length=32,choices=STATUS,default='submitted',db_index=True)
 extraction=models.JSONField(default=dict,blank=True); ai_recommendation=models.JSONField(default=dict,blank=True)
 assigned_to=models.CharField(max_length=180,blank=True); decision_reason=models.TextField(blank=True); version=models.PositiveIntegerField(default=1)
 class Meta: indexes=[models.Index(fields=['tenant_id','status','-created_at'],name='onboard_tenant_status_idx')]
 def __str__(self): return f'{self.worker_name} · {self.status}'

def document_path(instance,filename): return f'tenants/{instance.tenant_id}/cases/{instance.case_id}/{instance.id}/{filename}'
class CaseDocument(TenantOwned):
 id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); case=models.ForeignKey(OnboardingCase,on_delete=models.CASCADE,related_name='documents'); document_type=models.CharField(max_length=80); file=models.FileField(upload_to=document_path,max_length=512); original_name=models.CharField(max_length=255); mime_type=models.CharField(max_length=100); size_bytes=models.PositiveBigIntegerField(); sha256=models.CharField(max_length=64); status=models.CharField(max_length=32,default='queued'); confidence=models.FloatField(default=0); extracted_fields=models.JSONField(default=dict,blank=True); warnings=models.JSONField(default=list,blank=True)
 class Meta: indexes=[models.Index(fields=['tenant_id','case','status'],name='doc_tenant_case_status_idx')]

class AuditEvent(TenantOwned):
 id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); case=models.ForeignKey(OnboardingCase,on_delete=models.CASCADE,related_name='audit_events'); actor_id=models.CharField(max_length=180); event_type=models.CharField(max_length=100); details=models.JSONField(default=dict); correlation_id=models.CharField(max_length=100,blank=True)
 class Meta: ordering=['created_at']; indexes=[models.Index(fields=['tenant_id','case','created_at'],name='audit_tenant_case_created_idx')]

class EventOutbox(models.Model):
 id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); tenant_id=models.CharField(max_length=100,db_index=True); event_type=models.CharField(max_length=160); aggregate_id=models.CharField(max_length=100); payload=models.JSONField(); created_at=models.DateTimeField(auto_now_add=True); published_at=models.DateTimeField(null=True,blank=True); attempts=models.PositiveIntegerField(default=0)
 class Meta: indexes=[models.Index(fields=['published_at','created_at'],name='outbox_pending_created_idx')]

class VoiceContact(TenantOwned):
 CONSENT_STATUS=[('unknown','Unknown'),('granted','Granted'),('revoked','Revoked')]
 id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); phone_number=models.CharField(max_length=16); consent_status=models.CharField(max_length=16,choices=CONSENT_STATUS,default='unknown'); consent_recorded_at=models.DateTimeField(null=True,blank=True); consent_source=models.CharField(max_length=120,blank=True); consent_reference=models.CharField(max_length=255,blank=True); suppressed=models.BooleanField(default=False); suppression_reason=models.CharField(max_length=255,blank=True); updated_by=models.CharField(max_length=180,blank=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['tenant_id','phone_number'],name='voice_tenant_phone_unique')]
  indexes=[models.Index(fields=['tenant_id','consent_status','suppressed'],name='voice_tenant_status_idx')]

class VoicePolicyAudit(models.Model):
 id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); contact=models.ForeignKey(VoiceContact,on_delete=models.PROTECT,related_name='policy_events'); tenant_id=models.CharField(max_length=100,db_index=True); actor_id=models.CharField(max_length=180); event_type=models.CharField(max_length=80); details=models.JSONField(default=dict); correlation_id=models.CharField(max_length=100,blank=True); created_at=models.DateTimeField(auto_now_add=True)
 class Meta: ordering=['created_at']; indexes=[models.Index(fields=['tenant_id','contact','created_at'],name='voice_audit_tenant_idx')]

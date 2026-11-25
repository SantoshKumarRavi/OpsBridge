from django.contrib import admin
from .models import OnboardingCase,CaseDocument,AuditEvent,EventOutbox,VoiceContact,VoicePolicyAudit
@admin.register(OnboardingCase)
class OnboardingCaseAdmin(admin.ModelAdmin):list_display=('worker_name','tenant_id','role','status','created_at');list_filter=('status','country');search_fields=('worker_name','email','tenant_id')
admin.site.register(CaseDocument);admin.site.register(AuditEvent);admin.site.register(EventOutbox)

@admin.register(VoiceContact)
class VoiceContactAdmin(admin.ModelAdmin):
 list_display=('phone_number','tenant_id','consent_status','suppressed','updated_by','updated_at'); list_filter=('tenant_id','consent_status','suppressed'); search_fields=('phone_number','tenant_id'); readonly_fields=('tenant_id','phone_number','consent_status','consent_recorded_at','consent_source','consent_reference','suppressed','suppression_reason','updated_by','created_at','updated_at')
 def has_add_permission(self,request):return False
 def has_change_permission(self,request,obj=None):return False
 def has_delete_permission(self,request,obj=None):return False

@admin.register(VoicePolicyAudit)
class VoicePolicyAuditAdmin(admin.ModelAdmin):
 list_display=('event_type','tenant_id','actor_id','created_at'); list_filter=('tenant_id','event_type'); readonly_fields=('contact','tenant_id','actor_id','event_type','details','correlation_id','created_at')
 def has_add_permission(self,request):return False
 def has_change_permission(self,request,obj=None):return False
 def has_delete_permission(self,request,obj=None):return False

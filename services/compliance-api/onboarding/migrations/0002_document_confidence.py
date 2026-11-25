from django.db import migrations,models
class Migration(migrations.Migration):
 dependencies=[('onboarding','0001_initial')]
 operations=[migrations.AddField(model_name='casedocument',name='confidence',field=models.FloatField(default=0))]

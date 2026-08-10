from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("documents", "0003_documentasset")]

    operations = [
        migrations.AddField(
            model_name="storeddocument",
            name="locked",
            field=models.BooleanField(default=False),
        ),
    ]

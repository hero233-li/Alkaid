from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jobs", "0004_mocktoolstate")]

    operations = [
        migrations.AddField(
            model_name="job",
            name="error_code",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]

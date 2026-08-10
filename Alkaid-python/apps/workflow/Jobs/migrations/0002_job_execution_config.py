from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jobs", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="job",
            name="execution_config_snapshot",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="job",
            name="execution_config_version",
            field=models.PositiveIntegerField(default=1),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jobs", "0002_job_execution_config")]

    operations = [
        migrations.AddIndex(
            model_name="job",
            index=models.Index(
                fields=["status", "deadline_at"],
                name="job_status_dead_idx",
            ),
        ),
    ]

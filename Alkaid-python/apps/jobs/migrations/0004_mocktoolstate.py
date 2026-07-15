from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jobs", "0003_job_status_deadline_index")]

    operations = [
        migrations.CreateModel(
            name="MockToolState",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("namespace", models.CharField(max_length=64)),
                ("key", models.CharField(max_length=255)),
                ("payload", models.JSONField(default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("namespace", "key"),
                        name="mock_state_namespace_key_uniq",
                    )
                ]
            },
        )
    ]

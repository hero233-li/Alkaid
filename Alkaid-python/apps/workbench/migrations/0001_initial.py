from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="WorkbenchHistory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(blank=True, default="", max_length=255)),
                ("method", models.CharField(max_length=16)),
                ("url", models.TextField()),
                ("request_headers", models.JSONField(default=dict)),
                ("request_payload", models.JSONField(default=dict)),
                ("response_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("duration_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("success", models.BooleanField(default=False)),
                ("error_message", models.TextField(blank=True, default="")),
                ("response_headers", models.JSONField(default=dict)),
                ("response_body", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        )
    ]

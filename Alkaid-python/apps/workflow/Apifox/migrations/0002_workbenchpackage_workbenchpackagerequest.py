import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("workbench", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="WorkbenchPackage",
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
                ("name", models.CharField(max_length=255)),
                ("source_filename", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="WorkbenchPackageRequest",
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
                ("position", models.PositiveIntegerField()),
                ("name", models.CharField(max_length=255)),
                ("method", models.CharField(max_length=16)),
                ("url", models.TextField()),
                ("request_payload", models.JSONField(default=dict)),
                ("response_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("response_headers", models.JSONField(default=dict)),
                ("response_body", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "package",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="requests",
                        to="workbench.workbenchpackage",
                    ),
                ),
            ],
            options={
                "ordering": ["position", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("package", "position"),
                        name="workbench_pkg_request_position_uniq",
                    )
                ],
            },
        ),
    ]

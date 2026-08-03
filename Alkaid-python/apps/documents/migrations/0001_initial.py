import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DocumentFolder",
            fields=[
                ("id", models.CharField(max_length=100, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField()),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="children",
                        to="documents.documentfolder",
                    ),
                ),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.CreateModel(
            name="StoredDocument",
            fields=[
                ("id", models.CharField(max_length=100, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255, unique=True)),
                ("content", models.TextField()),
                ("size", models.PositiveBigIntegerField(default=0)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("document", "文档"),
                            ("multidimensional-table", "多维表格"),
                            ("spreadsheet", "在线表格"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[("created", "创建"), ("opened", "打开")], max_length=16
                    ),
                ),
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
                ("last_opened_at", models.DateTimeField()),
                (
                    "folder",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="documents",
                        to="documents.documentfolder",
                    ),
                ),
            ],
            options={"ordering": ["-last_opened_at", "-updated_at", "name"]},
        ),
        migrations.AddIndex(
            model_name="documentfolder",
            index=models.Index(fields=["parent", "name"], name="doc_folder_parent_name"),
        ),
        migrations.AddIndex(
            model_name="storeddocument",
            index=models.Index(fields=["kind", "-updated_at"], name="doc_kind_updated"),
        ),
        migrations.AddIndex(
            model_name="storeddocument",
            index=models.Index(fields=["folder", "name"], name="doc_folder_name"),
        ),
    ]

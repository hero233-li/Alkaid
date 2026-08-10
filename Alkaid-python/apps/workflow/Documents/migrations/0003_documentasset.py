import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("documents", "0002_add_word_document_kind")]

    operations = [
        migrations.CreateModel(
            name="DocumentAsset",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("content_type", models.CharField(max_length=127)),
                ("size", models.PositiveBigIntegerField()),
                ("content", models.BinaryField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "document",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assets",
                        to="documents.storeddocument",
                    ),
                ),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="documentasset",
            index=models.Index(fields=["document", "created_at"], name="doc_asset_created"),
        ),
    ]

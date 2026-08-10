import hashlib

from django.db import migrations, models


def endpoint_key(method: str, url: str) -> str:
    identity = f"{method.upper()}\n{url}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def populate_endpoint_keys(apps, schema_editor) -> None:
    WorkbenchHistory = apps.get_model("workbench", "WorkbenchHistory")
    seen: set[str] = set()
    for history in WorkbenchHistory.objects.order_by("-created_at", "-id").iterator():
        key = endpoint_key(history.method, history.url)
        if key in seen:
            history.delete()
            continue
        seen.add(key)
        WorkbenchHistory.objects.filter(pk=history.pk).update(
            endpoint_key=key,
            updated_at=history.created_at,
        )


class Migration(migrations.Migration):
    dependencies = [("workbench", "0002_workbenchpackage_workbenchpackagerequest")]

    operations = [
        migrations.AddField(
            model_name="workbenchhistory",
            name="endpoint_key",
            field=models.CharField(max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="workbenchhistory",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, db_index=True),
        ),
        migrations.RunPython(populate_endpoint_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="workbenchhistory",
            name="endpoint_key",
            field=models.CharField(max_length=64, unique=True),
        ),
        migrations.AlterModelOptions(
            name="workbenchhistory",
            options={"ordering": ["-updated_at", "-id"]},
        ),
    ]

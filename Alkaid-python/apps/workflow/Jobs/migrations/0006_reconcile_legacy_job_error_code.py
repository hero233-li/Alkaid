from django.db import migrations, models


def ensure_legacy_error_code(apps, schema_editor):
    job = apps.get_model("jobs", "Job")
    table = job._meta.db_table
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        columns = {
            column.name for column in connection.introspection.get_table_description(cursor, table)
        }
    if "error_code" in columns:
        return
    quoted_table = schema_editor.quote_name(table)
    quoted_column = schema_editor.quote_name("error_code")
    schema_editor.execute(
        f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} varchar(128) NOT NULL DEFAULT ''"
    )


class Migration(migrations.Migration):
    dependencies = [("jobs", "0005_delete_mocktoolstate")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    ensure_legacy_error_code,
                    reverse_code=migrations.RunPython.noop,
                )
            ],
            state_operations=[
                migrations.AddField(
                    model_name="job",
                    name="error_code",
                    field=models.CharField(
                        blank=True,
                        default="",
                        max_length=128,
                    ),
                )
            ],
        )
    ]

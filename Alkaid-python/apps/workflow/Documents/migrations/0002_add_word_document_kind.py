from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("documents", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="storeddocument",
            name="kind",
            field=models.CharField(
                choices=[
                    ("document", "文档"),
                    ("word", "在线 Word"),
                    ("multidimensional-table", "多维表格"),
                    ("spreadsheet", "在线表格"),
                ],
                max_length=32,
            ),
        ),
    ]

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("jobs", "0004_mocktoolstate")]

    operations = [migrations.DeleteModel(name="MockToolState")]

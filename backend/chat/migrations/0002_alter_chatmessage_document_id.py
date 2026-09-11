from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="chatmessage",
            name="document_id",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]

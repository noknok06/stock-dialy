from django.db import migrations


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE stockdiary_diarynote ADD COLUMN IF NOT EXISTS source_doc_id VARCHAR(8) NULL DEFAULT NULL;",
            reverse_sql="ALTER TABLE stockdiary_diarynote DROP COLUMN IF EXISTS source_doc_id;",
        ),
    ]

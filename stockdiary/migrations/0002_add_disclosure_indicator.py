from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stockdiary', '0001_add_source_doc_id'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE stockdiary_stockdiary
                    ADD COLUMN IF NOT EXISTS latest_disclosure_date DATE NULL DEFAULT NULL,
                    ADD COLUMN IF NOT EXISTS latest_disclosure_doc_type_name VARCHAR(50) NOT NULL DEFAULT '';
            """,
            reverse_sql="""
                ALTER TABLE stockdiary_stockdiary
                    DROP COLUMN IF EXISTS latest_disclosure_date,
                    DROP COLUMN IF EXISTS latest_disclosure_doc_type_name;
            """,
        ),
    ]

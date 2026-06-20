from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stockdiary', '0016_thesis_basis_and_claim_500'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='diarynote',
            name='importance',
        ),
    ]

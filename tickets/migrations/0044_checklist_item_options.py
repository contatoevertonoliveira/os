from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('tickets', '0043_checklist_advanced'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChecklistTemplateItemOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=200, verbose_name='Rótulo')),
                ('field_type', models.CharField(choices=[('text', 'Texto (input)'), ('textarea', 'Texto (área)'), ('number', 'Número'), ('date', 'Data'), ('select', 'Select'), ('radio', 'Radio'), ('checkbox', 'Checkbox'), ('switch', 'Switch'), ('button', 'Botão')], default='text', max_length=20, verbose_name='Tipo')),
                ('is_required', models.BooleanField(default=False, verbose_name='Obrigatório')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Ordem')),
                ('options_text', models.TextField(blank=True, help_text='Uma opção por linha (Select/Radio).', null=True, verbose_name='Opções')),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='options', to='tickets.checklisttemplateitem', verbose_name='Atividade')),
            ],
            options={
                'verbose_name': 'Opção do Item',
                'verbose_name_plural': 'Opções dos Itens',
                'ordering': ['order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='DailyChecklistItemOptionValue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value_text', models.TextField(blank=True, null=True, verbose_name='Valor (texto)')),
                ('value_bool', models.BooleanField(blank=True, null=True, verbose_name='Valor (booleano)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('daily_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='option_values', to='tickets.dailychecklistitem', verbose_name='Item do Checklist')),
                ('template_option', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='daily_values', to='tickets.checklisttemplateitemoption', verbose_name='Opção do Modelo')),
            ],
            options={
                'verbose_name': 'Valor de Opção',
                'verbose_name_plural': 'Valores de Opções',
                'unique_together': {('daily_item', 'template_option')},
            },
        ),
    ]


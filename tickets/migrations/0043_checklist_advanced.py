from django.db import migrations, models
import django.db.models.deletion


def forwards_fill_checklist_fields(apps, schema_editor):
    ChecklistTemplateItem = apps.get_model('tickets', 'ChecklistTemplateItem')
    DailyChecklistItem = apps.get_model('tickets', 'DailyChecklistItem')

    ChecklistTemplateItem.objects.filter(field_type__isnull=True).update(field_type='switch')
    ChecklistTemplateItem.objects.filter(is_required__isnull=True).update(is_required=True)

    for d in DailyChecklistItem.objects.all().iterator():
        changed = False
        if getattr(d, 'field_type', None) in (None, ''):
            template_item = getattr(d, 'template_item', None)
            d.field_type = getattr(template_item, 'field_type', None) or 'switch'
            changed = True
        if getattr(d, 'is_required', None) is None:
            template_item = getattr(d, 'template_item', None)
            d.is_required = getattr(template_item, 'is_required', None)
            if d.is_required is None:
                d.is_required = True
            changed = True
        if getattr(d, 'select_options', None) is None:
            template_item = getattr(d, 'template_item', None)
            d.select_options = getattr(template_item, 'select_options', None)
            changed = True
        if getattr(d, 'order', None) in (None, 0):
            template_item = getattr(d, 'template_item', None)
            template_order = getattr(template_item, 'order', None)
            if template_order is not None:
                d.order = template_order
                changed = True
        if changed:
            d.save(update_fields=['field_type', 'is_required', 'select_options', 'order'])


def backwards_noop(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ('tickets', '0042_access_control'),
    ]

    operations = [
        migrations.AddField(
            model_name='checklisttemplate',
            name='client',
            field=models.ForeignKey(blank=True, help_text='Se selecionado, este modelo aparece como opção somente para este cliente.', null=True, on_delete=django.db.models.deletion.SET_NULL, to='tickets.client', verbose_name='Empresa/Cliente'),
        ),
        migrations.AddField(
            model_name='checklisttemplateitem',
            name='field_type',
            field=models.CharField(choices=[('group', 'Grupo'), ('checkbox', 'Checkbox'), ('switch', 'Switch'), ('select', 'Select'), ('text', 'Texto')], default='switch', max_length=20, verbose_name='Tipo do Campo'),
        ),
        migrations.AddField(
            model_name='checklisttemplateitem',
            name='is_required',
            field=models.BooleanField(default=True, verbose_name='Obrigatório'),
        ),
        migrations.AddField(
            model_name='checklisttemplateitem',
            name='parent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='tickets.checklisttemplateitem', verbose_name='Item Pai'),
        ),
        migrations.AddField(
            model_name='checklisttemplateitem',
            name='select_options',
            field=models.TextField(blank=True, help_text='Uma opção por linha (somente para tipo Select).', null=True, verbose_name='Opções do Select'),
        ),
        migrations.AddField(
            model_name='dailychecklistitem',
            name='field_type',
            field=models.CharField(choices=[('group', 'Grupo'), ('checkbox', 'Checkbox'), ('switch', 'Switch'), ('select', 'Select'), ('text', 'Texto')], default='switch', max_length=20, verbose_name='Tipo do Campo'),
        ),
        migrations.AddField(
            model_name='dailychecklistitem',
            name='is_required',
            field=models.BooleanField(default=True, verbose_name='Obrigatório'),
        ),
        migrations.AddField(
            model_name='dailychecklistitem',
            name='order',
            field=models.PositiveIntegerField(default=0, verbose_name='Ordem'),
        ),
        migrations.AddField(
            model_name='dailychecklistitem',
            name='parent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='tickets.dailychecklistitem', verbose_name='Item Pai'),
        ),
        migrations.AddField(
            model_name='dailychecklistitem',
            name='select_options',
            field=models.TextField(blank=True, null=True, verbose_name='Opções do Select'),
        ),
        migrations.AddField(
            model_name='dailychecklistitem',
            name='value_text',
            field=models.TextField(blank=True, null=True, verbose_name='Valor'),
        ),
        migrations.RunPython(forwards_fill_checklist_fields, backwards_noop),
    ]


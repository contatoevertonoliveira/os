
with open(r'c:\Users\EvertonOliveira\Documents\Systems\Python\os\templates\tickets\ticket_modal_body.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_str = '{{ update.created_by.get_full_name|default:update.created_by.username }}'
new_str = "{% if update.created_by %}{{ update.created_by.get_full_name|default:update.created_by.username }}{% else %}Sistema{% endif %}"

content = content.replace(old_str, new_str)

with open(r'c:\Users\EvertonOliveira\Documents\Systems\Python\os\templates\tickets\ticket_modal_body.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Arquivo atualizado com sucesso!')

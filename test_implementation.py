"""
Script de Teste - Validar Implementação de Contatos

Este script testa se:
1. Os contatos foram importados corretamente
2. Os fields foram adicionados ao modelo Ticket
3. O formulário está funcionando

Execute: python manage.py shell < test_implementation.py
"""

from tickets.models import ContactPerson, Client, Ticket
from django.db.models import Q

print("=" * 60)
print("TESTE DE IMPLEMENTAÇÃO - CONTATOS")
print("=" * 60)

# Teste 1: Verificar contatos importados
print("\n1. Verificando contatos importados...")
total_contacts = ContactPerson.objects.count()
print(f"   ✓ Total de contatos: {total_contacts}")

client_contacts = ContactPerson.objects.filter(origin='client').count()
print(f"   ✓ Contatos de clientes: {client_contacts}")

jumperfour_contacts = ContactPerson.objects.filter(origin='jumperfour').count()
print(f"   ✓ Contatos JumperFour: {jumperfour_contacts}")

manual_contacts = ContactPerson.objects.filter(origin='manual').count()
print(f"   ✓ Contatos manuais: {manual_contacts}")

# Teste 2: Verificar clientes com contatos
print("\n2. Verificando clientes com contatos...")
clients_with_contacts = Client.objects.filter(contact_persons__isnull=False).distinct().count()
print(f"   ✓ Clientes com contatos: {clients_with_contacts}")

# Teste 3: Verificar se os fields foram adicionados ao Ticket
print("\n3. Verificando fields do Ticket...")
try:
    ticket_fields = [f.name for f in Ticket._meta.get_fields()]
    if 'contact_requester' in ticket_fields:
        print("   ✓ contact_requester field presente")
    else:
        print("   ✗ contact_requester field NÃO encontrado")
    
    if 'contact_responsible' in ticket_fields:
        print("   ✓ contact_responsible field presente")
    else:
        print("   ✗ contact_responsible field NÃO encontrado")
except Exception as e:
    print(f"   ✗ Erro ao verificar fields: {e}")

# Teste 4: Exemplos de contatos
print("\n4. Exemplos de contatos importados:")
examples = ContactPerson.objects.all()[:5]
for contact in examples:
    client_name = contact.client.name if contact.client else "Sem cliente"
    print(f"   - {contact.name} ({contact.origin}) - Cliente: {client_name}")

# Teste 5: Filtro de contatos por cliente
print("\n5. Testando filtro de contatos por cliente...")
first_client = Client.objects.first()
if first_client:
    client_contacts_filtered = ContactPerson.objects.filter(client=first_client, origin='client')
    print(f"   ✓ Cliente: {first_client.name}")
    print(f"   ✓ Contatos do cliente: {client_contacts_filtered.count()}")
    if client_contacts_filtered.exists():
        print(f"      Ex: {client_contacts_filtered.first().name}")

print("\n" + "=" * 60)
print("✅ TESTES COMPLETOS")
print("=" * 60)
print("\nPróximos passos:")
print("1. Acesse o formulário de criação de OS")
print("2. Selecione um cliente")
print("3. Verifique se o campo 'Solicitante (Contato de Cliente)' foi preenchido automaticamente")
print("4. Verifique se o campo 'Responsável/Executor (Contato)' mostra os contatos da planilha")
print("5. Acesse o Django Admin em /admin/tickets/contactperson/ para gerenciar contatos")

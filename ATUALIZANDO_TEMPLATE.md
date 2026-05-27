# Guia: Atualizando o Template HTML do Formulário de OS

## 📝 Resumo

O formulário Django foi atualizado com os novos campos `contact_requester` e `contact_responsible`. 
Se você quiser exibir esses campos na interface, siga as instruções abaixo.

## 🎯 Localização dos Templates

Os templates do formulário de OS estão em:
- `templates/tickets/ticket_form.html` (ou similar)

## ✏️ Exemplo de Atualização

### 1. Adicionar Campo "Solicitante (Contato de Cliente)"

Se seu template atual mostra solicitantes assim:

```html
<!-- ANTES - Apenas usuários do sistema -->
<div class="form-group">
    <label for="id_requester_selection">Solicitante</label>
    {{ form.requester_selection }}
</div>
```

Atualize para:

```html
<!-- DEPOIS - Com contatos de cliente -->
<div class="form-group">
    <label for="id_contact_requester">Solicitante (Contato de Cliente)</label>
    {{ form.contact_requester }}
    <small class="form-text text-muted">
        Selecione um contato do cliente. Lista auto-filtrada por cliente selecionado.
    </small>
</div>

<!-- Opcional: Manter a opção de usuários do sistema -->
<div class="form-group">
    <label for="id_requester_selection">Solicitante (Usuário Sistema)</label>
    {{ form.requester_selection }}
</div>
```

### 2. Adicionar Campo "Responsável/Executor (Contato)"

Se seu template atual mostra responsáveis assim:

```html
<!-- ANTES - Apenas usuários do sistema -->
<div class="form-group">
    <label for="id_technician_selection">Responsável</label>
    {{ form.technician_selection }}
</div>
```

Atualize para:

```html
<!-- DEPOIS - Com contatos da planilha -->
<div class="form-group">
    <label for="id_contact_responsible">Responsável/Executor (Contato)</label>
    {{ form.contact_responsible }}
    <small class="form-text text-muted">
        Selecione um responsável da planilha JumperFour ou contato manual.
    </small>
</div>

<!-- Opcional: Manter a opção de usuários do sistema -->
<div class="form-group">
    <label for="id_technician_selection">Responsável (Usuário Sistema)</label>
    {{ form.technician_selection }}
</div>
```

## 🎨 Exemplo Completo com Bootstrap

```html
<div class="row">
    <div class="col-md-6">
        <div class="form-group">
            <label for="id_contact_requester">
                <strong>Solicitante (Contato de Cliente)</strong>
                <span class="badge badge-info">Novo</span>
            </label>
            {% if form.contact_requester %}
                {{ form.contact_requester }}
                {% if form.contact_requester.errors %}
                    <div class="alert alert-danger mt-2">
                        {{ form.contact_requester.errors }}
                    </div>
                {% endif %}
            {% else %}
                <p class="text-muted">Selecione um cliente para exibir contatos</p>
            {% endif %}
            <small class="form-text text-muted d-block mt-2">
                👥 Contato principal do cliente que está solicitando a OS.
            </small>
        </div>
    </div>

    <div class="col-md-6">
        <div class="form-group">
            <label for="id_contact_responsible">
                <strong>Responsável/Executor</strong>
                <span class="badge badge-success">Novo</span>
            </label>
            {% if form.contact_responsible %}
                {{ form.contact_responsible }}
                {% if form.contact_responsible.errors %}
                    <div class="alert alert-danger mt-2">
                        {{ form.contact_responsible.errors }}
                    </div>
                {% endif %}
            {% endif %}
            <small class="form-text text-muted d-block mt-2">
                📋 Responsável pela execução da OS (da planilha JumperFour).
            </small>
        </div>
    </div>
</div>
```

## 🔗 JavaScript Enhancements (Opcional)

Se quiser criar um filtro dinâmico quando o cliente é selecionado:

```javascript
// Atualizar contatos quando cliente é selecionado
document.getElementById('id_client').addEventListener('change', function() {
    const clientId = this.value;
    
    if (clientId) {
        // Fazer requisição para atualizar contatos
        fetch(`/api/contacts/client/${clientId}/`, {
            headers: {'X-CSRFToken': getCookie('csrftoken')}
        })
        .then(r => r.json())
        .then(data => {
            const select = document.getElementById('id_contact_requester');
            select.innerHTML = '<option value="">Selecione um solicitante...</option>';
            data.forEach(contact => {
                const option = document.createElement('option');
                option.value = contact.id;
                option.textContent = contact.name;
                select.appendChild(option);
            });
        });
    } else {
        // Limpar select
        document.getElementById('id_contact_requester').innerHTML = 
            '<option value="">Selecione um cliente primeiro...</option>';
    }
});
```

## 📋 Checklist de Implementação

- [ ] Localizar o arquivo do template (ticket_form.html)
- [ ] Adicionar os novos campos (`contact_requester` e `contact_responsible`)
- [ ] Testar no navegador
- [ ] Verificar se os fields aparecem corretamente
- [ ] Testar a seleção de cliente e filtragem automática
- [ ] Testar a seleção de contatos
- [ ] Verificar validação de formulário
- [ ] Testar salvamento da OS com os novos campos

## 🧪 Como Testar

1. Abra a página de criação de OS
2. Selecione um cliente que tenha contatos
3. Verifique se o campo "Solicitante (Contato de Cliente)" foi preenchido
4. Selecione um contato do cliente
5. Selecione um contato responsável
6. Salve o formulário
7. Acesse o registro criado e verifique se os contatos foram salvos

## ⚠️ Notas Importantes

- Os novos fields são **opcionais** (não obrigatórios)
- Você pode manter os campos antigos de usuários simultaneamente
- O filtro automático por cliente é feito pelo backend (sem JavaScript necessário inicialmente)
- Se usar JavaScript no frontend, configure um endpoint de API para retornar contatos

## 📞 Exemplo de Endpoint de API (Opcional)

```python
# tickets/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET

@require_GET
def get_client_contacts(request, client_id):
    """API para retornar contatos de um cliente"""
    from tasks.models import ContactPerson
    contacts = ContactPerson.objects.filter(client_id=client_id, origin='client')
    return JsonResponse(list(contacts.values('id', 'name', 'email', 'phone')), safe=False)

# tickets/urls.py
path('api/contacts/client/<int:client_id>/', get_client_contacts, name='get-client-contacts'),
```

---

Para dúvidas, consulte `CONTATOS_IMPLEMENTATION.md` ou `DEMANDA_CONCLUIDA.md`

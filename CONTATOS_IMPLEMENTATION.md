# Implementação: Contatos para OS (Solicitante e Responsável)

## Resumo das Mudanças

### 1. Novo Modelo: `ContactPerson`
- **Arquivo**: `tickets/models.py`
- **Descrição**: Novo model para gerenciar contatos que não estão vinculados a usuários do sistema
- **Campos principais**:
  - `name`: Nome do contato
  - `email`: Email (opcional)
  - `phone`: Telefone (opcional)
  - `client`: Referência ao cliente (permite identificar de qual cliente o contato é)
  - `origin`: Origem do contato ('client', 'jumperfour', 'manual')
  - `is_active`: Flag para marcar contatos ativos/inativos

### 2. Campos Adicionados ao Ticket
- `contact_requester`: ForeignKey para ContactPerson - Solicitante (Contato de Cliente)
- `contact_responsible`: ForeignKey para ContactPerson - Responsável/Executor (Contato)

### 3. Importação de Contatos
- **Script**: `tickets/management/commands/import_contacts.py`
- **Função**: Importa automaticamente:
  - Contatos dos clientes cadastrados (contact1 e contact2)
  - Contatos da planilha `data/JUMPERFOUR.xlsx`
- **Uso**: `python manage.py import_contacts`

### 4. Atualizações no Formulário
- **Arquivo**: `tickets/forms.py`
- **Novo fields**:
  - `contact_requester`: Select com contatos de clientes
  - `contact_responsible`: Select com contatos da planilha + contatos manuais
- **Filtro automático**: Os contatos de "Solicitante" são filtrados automaticamente quando um cliente é selecionado

### 5. Django Admin
- **Arquivo**: `tickets/admin.py`
- **Novo registro**: `ContactPersonAdmin` para gerenciar contatos via admin
- **Funcionalidades**:
  - Listar todos os contatos com origem, status ativo/inativo
  - Filtrar por origem, cliente, status
  - Buscar por nome, email, telefone

## Como Usar

### 1. Importar Contatos
```bash
python manage.py import_contacts
```
Isso importará:
- 69 contatos dos clientes cadastrados
- 136 contatos da planilha JumperFour.xlsx
- Total: 205 contatos

### 2. Acessar via Interface
1. Abra o formulário de cadastro de OS
2. Após selecionar um cliente, o campo "Solicitante (Contato de Cliente)" será automaticamente filtrado para mostrar apenas os contatos daquele cliente
3. O campo "Responsável/Executor (Contato)" mostra todos os contatos da planilha JumperFour

### 3. Gerenciar Contatos
- Django Admin: `/admin/tickets/contactperson/`
- Visualizar, editar, deletar contatos
- Criar novos contatos manualmente

## Fluxo de Dados

```
Clientes Cadastrados → Contatos Extraídos → ContactPerson (origin='client')
                                                    ↓
Adicionar ao Ticket como "Solicitante"

Planilha JUMPERFOUR.xlsx → Contatos Parseados → ContactPerson (origin='jumperfour')
                                                   ↓
                           Adicionar ao Ticket como "Responsável/Executor"

Manual Entry → ContactPerson (origin='manual')
                     ↓
         Adicionar ao Ticket como "Responsável/Executor"
```

## Estrutura do Banco de Dados

### Tabela: ContactPerson
| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | Integer | ID único |
| name | CharField(200) | Nome do contato |
| email | EmailField | Email (nullable) |
| phone | CharField(20) | Telefone (nullable) |
| client_id | ForeignKey | Referência ao cliente |
| origin | CharField | Origem (client, jumperfour, manual) |
| is_active | BooleanField | Status ativo |
| created_at | DateTime | Data de criação |
| updated_at | DateTime | Data de atualização |

### Tabela: Ticket (novas colunas)
| Campo | Tipo | Descrição |
|-------|------|-----------|
| contact_requester_id | ForeignKey | Contato solicitante |
| contact_responsible_id | ForeignKey | Contato responsável/executor |

## Migrações Realizadas

1. **0054**: Criação do modelo ContactPerson e adição dos campos ao Ticket
2. **0055**: Remoção do unique_together do ContactPerson (para permitir duplicações legítimas)

## Permissões & Segurança

- Contatos não estão vinculados a usuários do sistema
- Qualquer contato pode ser selecionado por qualquer usuário
- Manage.py command para importação é restrito a staff (use controle de acesso Django)

## Próximas Melhorias (Opcional)

1. Adicionar validação de email duplicate
2. Adicionar fields adicionais (departamento, ramal)
3. Criar UI para editar contatos inline na criação de OS
4. Fila de importação automática da planilha

## Contato & Suporte

Para dúvidas ou problemas na importação, execute:
```bash
python manage.py import_contacts --help
```

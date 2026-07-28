# 🔄 Mapeamento de Dados: JumperFour → Odoo

**Versão:** 1.0  
**Data:** 22/07/2026  
**Status:** Em Elaboração

---

## 📋 Índice de Mapeamentos

1. [Autenticação & Usuários](#autenticacao--usuarios)
2. [Clientes & Contatos](#clientes--contatos)
3. [Equipamentos & Categorias](#equipamentos--categorias)
4. [Ordens de Serviço (CORE)](#ordens-de-servico-core)
5. [Viagens Técnicas](#viagens-tecnicas)
6. [Chat IA](#chat-ia)
7. [Otros (Chat Privado, Checklists, etc)](#otros)

---

## Autenticação & Usuários

### User (Django) → res.users (Odoo)

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `username` | `login` | String | Campo de autenticação |
| `email` | `email` | Email | Email do usuário |
| `first_name` | `name` (parte 1) | String | Nome |
| `last_name` | `name` (parte 2) | String | Sobrenome |
| `is_active` | `active` | Boolean | Status do usuário |
| `is_staff` | N/A | - | Django-specific, ignorar |
| `is_superuser` | `is_superuser` | Boolean | Admin |
| `date_joined` | N/A | - | Não migrar (Odoo usa create_date) |
| `last_login` | N/A | - | Não migrar |

**Críticos:** username, email, name  
**Ação:** Criar novo usuário em Odoo com mesmas credenciais  

---

### UserProfile → hr.employee (Odoo)

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `role` (code) | `groups_id` | Many2Many | Mapear RoleLevel para grupo Odoo |
| `job_title` | `job_title` | String | Cargo do funcionário |
| `station` | `work_location_id` | Many2One | Local de trabalho |
| `department` | `department_id` | Many2One | Departamento |
| `personal_phone` | `phone` | String | Telefone pessoal |
| `company_phone` | `work_phone` | String | Telefone empresa |
| `supervisor` | `parent_id` | Many2One | Referência hierárquica |
| `technician_type` | `job_id.technician_type` | Selection | Tipo: fixo/volante |
| `fixed_client` | `partner_id` | Many2One | Cliente fixo (se volante) |
| `blocked_until` | `active` | Boolean | Se bloqueado, ativo=False |
| `ai_chat_enabled` | Custom field | Boolean | Campo customizado Odoo |
| `voice_wakeword_enabled` | Custom field | Boolean | Campo customizado Odoo |
| `tts_enabled` | Custom field | Boolean | Campo customizado Odoo |

**Críticos:** role, job_title, department  
**Ação:** Criar employee Odoo com dados de UserProfile  
**Scripts Necessários:**
- Criar `hr.employee` a partir de `User` + `UserProfile`
- Mapear RoleLevel → res.groups
- Atualizar relacionamentos supervisor

---

### RoleLevel → res.groups (Odoo)

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `code` | `code` | String | Código único |
| `name` | `name` | String | Nome do grupo |
| `is_system` | N/A | - | Odoo não tem este campo |
| `is_active` | N/A | - | Usar `users` empty para desativar |

**Críticos:** code, name  
**Ação:** Criar res.groups no Odoo, mapear usuários  

---

## Clientes & Contatos

### Client → res.partner (is_company=True)

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `name` | `name` | String | Nome da empresa |
| `email` | `email` | Email | Email principal |
| `phone` | `phone` | String | Telefone |
| `address` | `street` | String | Endereço |
| `city` | `city` | String | Cidade |
| `state` | `state_id` | Many2One | Estado/Região |
| `zip` | `zip` | String | CEP/Postal |
| `country` | `country_id` | Many2One | País |
| `cnpj` | Custom field | String | Campo customizado |
| `is_active` | `active` | Boolean | Status |
| `created_at` | N/A | - | Usar create_date Odoo |

**Críticos:** name, email, phone  
**Ação:** Criar res.partner com is_company=True  
**Validações:**
- CNPJ pode ser campo customizado
- Validar relacionamentos com hubs

---

### ClientHub → res.partner.address

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `name` | `name` | String | Nome do hub/filial |
| `client` | `parent_id` | Many2One | Referência ao cliente principal |
| `address` | `street` | String | Endereço |
| `city` | `city` | String | Cidade |
| `phone` | `phone` | String | Telefone |

**Críticos:** name, parent_id (client)  
**Ação:** Criar res.partner com parent_id apontando para cliente  

---

### ContactClient → res.partner.contact

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `name` | `name` | String | Nome do contato |
| `client` | `parent_id` | Many2One | Cliente relacionado |
| `email` | `email` | Email | Email |
| `phone` | `phone` | String | Telefone |
| `title` | `title` | Selection | Título (Sr./Sra.) |
| `role` | `function` | String | Função/Cargo |

**Críticos:** name, parent_id, phone  
**Ação:** Criar res.partner tipo contact com parent_id = cliente  

---

### ContactJumper → res.partner.contact (interno)

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `name` | `name` | String | Nome |
| `email` | `email` | Email | Email |
| `phone` | `phone` | String | Telefone |
| `user` | `user_id` | Many2One | Usuário Odoo |

**Críticos:** name, email  
**Ação:** Criar res.partner ou usar hr.employee diretamente  

---

## Equipamentos & Categorias

### Equipment → product.product (type="service")

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `name` | `name` | String | Nome do equipamento/serviço |
| `description` | `description` | Text | Descrição |
| `type` | `type` | Selection | Sempre "service" |
| `category` | `categ_id` | Many2One | Categoria |

**Críticos:** name, type (sempre "service")  
**Ação:** Criar product.product com type=service  

---

### EquipmentType → product.category

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `name` | `name` | String | Nome da categoria |

**Nota:** EquipmentType está vazio em JumperFour (0 registros)  
**Ação:** Criar categorias padrão em Odoo  

---

### OrderType → Tag ou Campo Customizado

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `name` | `x_order_type` | String | Campo customizado em helpdesk.ticket |

**Nota:** Apenas 1 registro  
**Ação:** Criar campo customizado ou usar tags  

---

### ProblemType → helpdesk.ticket.category

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `name` | `name` | String | Nome da categoria |
| `icon` | N/A | - | Não mapeia, usar cor em Odoo |

**Críticos:** name  
**Ação:** Criar helpdesk.ticket.category  

---

### System → helpdesk.ticket.tag

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `name` | `name` | String | Nome do sistema |

**Críticos:** name  
**Ação:** Criar helpdesk.ticket.tag para cada sistema  

---

### TicketType → Pode ser Tag ou Campo Customizado

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `name` | `x_ticket_type` | String | Campo customizado |

**Ação:** Criar campo customizado em helpdesk.ticket  

---

## Ordens de Serviço (CORE)

### Ticket → helpdesk.ticket ⭐ CRÍTICO

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `id` | N/A | - | Não mapear, Odoo gera novo |
| `code` | `name` | String | Número da OS |
| `title` | `name` (append) | String | Descrição breve |
| `description` | `description` | Text | Descrição completa |
| `client` | `partner_id` | Many2One | Cliente |
| `client_hub` | N/A | - | Será contact do cliente |
| `status` | `stage_id` | Many2One | Status/etapa |
| `priority` | `priority` | Selection | Prioridade (low/med/high) |
| `assigned_to` | `user_id` | Many2One | Técnico atribuído |
| `created_at` | `create_date` | DateTime | Data de criação |
| `updated_at` | `write_date` | DateTime | Data de atualização |
| `due_date` | `deadline` | Date | Data limite |
| `attachments` | `attachment_ids` | One2Many | Imagens/anexos |
| `tags` | `tag_ids` | Many2Many | Sistemas/Tipos |

**Críticos:** code, title, partner_id, stage_id, assigned_to  
**Ação:** Criar helpdesk.ticket com dados mapeados  
**Validações:**
- Validar que cliente existe em Odoo
- Validar que técnico existe em Odoo
- Validar que status existe em Odoo

---

### TicketStatus → helpdesk.ticket.stage

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `name` | `name` | String | Nome do status |
| `color` | `legend_priority` | String | Cor (se aplicável) |
| `icon` | N/A | - | Não mapeia |

**Críticos:** name  
**Ação:** Criar helpdesk.ticket.stage com mesmo nome  

---

### TicketImage → ir.attachment

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `image` | `datas` | Binary | Arquivo da imagem |
| `ticket` | N/A | - | Será vinculado ao ticket |
| `created_at` | `create_date` | DateTime | Data |

**Críticos:** datas (conteúdo do arquivo)  
**Ação:** Copiar arquivo binário para ir.attachment  

---

### TicketUpdate → helpdesk.ticket.message (via mail.message)

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `ticket` | `res_id` | Integer | Ticket relacionado |
| `description` | `body` | Html | Mensagem |
| `author` | `author_id` | Many2One | Autor |
| `created_at` | `create_date` | DateTime | Data |

**Críticos:** body, author_id  
**Ação:** Usar mail.message ou comentários Odoo  

---

## Viagens Técnicas

### TechnicianTravel → hr.expense (ou custom)

| JumperFour | Odoo | Tipo | Observações |
|-----------|------|------|-------------|
| `technician` | `employee_id` | Many2One | Funcionário |
| `start_date` | `date` | Date | Data de início |
| `end_date` | N/A | - | Será calculada |
| `segments` | `expense_line_ids` | One2Many | Segmentos |

**Nota:** Nenhum dado em JumperFour (0 registros)  
**Ação:** Pular migração, criar modelo custom se necessário  

---

## Chat IA

### AIChatSession → Custom Model (manter em Django)

Não mapeia bem para Odoo. Recomendação: **manter no Django ou criar modelo custom em Odoo**.

| JumperFour | Odoo | Tipo |
|-----------|------|------|
| `user` | user_id | Many2One |
| `session_data` | N/A | - |
| `messages` | `message_ids` | One2Many |

**Ação:** Manter em Django com integração via webhook  

---

## Otros

### PrivateChatThread → mail.activity (ou custom)

| JumperFour | Odoo | Tipo |
|-----------|------|------|
| `participants` | `user_ids` | Many2Many |
| `messages` | `activity_ids` | One2Many |

**Ação:** Usar mail.activity Odoo ou manter Django  

---

### DailyChecklist → helpdesk.sla (ou custom)

| JumperFour | Odoo | Tipo |
|-----------|------|------|
| `name` | `name` | String |
| `items` | `line_ids` | One2Many |

**Ação:** Mapear para helpdesk.sla ou criar modelo custom  

---

### ShiftHandover → Custom Model

| JumperFour | Odoo | Tipo |
|-----------|------|------|
| `user` | `user_id` | Many2One |
| `shift_date` | `shift_date` | Date |

**Ação:** Criar modelo custom em Odoo (jumperfour_custom)  

---

## 📊 Resumo de Criticidade

### 🔴 CRÍTICO (Obrigatório Migrar)
- ✅ User → res.users
- ✅ UserProfile → hr.employee
- ✅ Client → res.partner
- ✅ ClientHub → res.partner (child)
- ✅ Equipment → product.product
- ✅ Ticket → helpdesk.ticket
- ✅ TicketStatus → helpdesk.ticket.stage

**Total:** ~200 registros

### 🟠 IMPORTANTE (Migrar se possível)
- ⚠️ ContactClient → res.partner.contact
- ⚠️ TicketImage → ir.attachment
- ⚠️ TicketUpdate → mail.message
- ⚠️ ProblemType → helpdesk.ticket.category
- ⚠️ System → helpdesk.ticket.tag

**Total:** ~150 registros

### 🟡 OPCIONAL (Manter em Django ou Custom)
- ℹ️ AIChatSession → Django custom
- ℹ️ PrivateChatThread → Django custom
- ℹ️ DailyChecklist → Django custom ou helpdesk.sla
- ℹ️ ShiftHandover → Custom Odoo module

**Total:** ~50 registros

---

## 🔧 Scripts de Migração Necessários

```python
1. migrate_users.py
   - User → res.users
   - UserProfile → hr.employee
   - RoleLevel → res.groups

2. migrate_clients.py
   - Client → res.partner
   - ClientHub → res.partner (child)
   - ContactClient → res.partner.contact

3. migrate_equipment.py
   - EquipmentType → product.category
   - Equipment → product.product
   - OrderType, ProblemType, System → tags/categorias

4. migrate_tickets.py
   - Ticket → helpdesk.ticket
   - TicketStatus → helpdesk.ticket.stage
   - TicketImage → ir.attachment
   - TicketUpdate → mail.message

5. migrate_custom.py
   - AIChatSession (opcional)
   - PrivateChatThread (opcional)
   - ShiftHandover (opcional)
```

---

## ✅ Próximas Ações

- [ ] **Validar mapeamento** com stakeholders
- [ ] **Refinar scripts** de migração
- [ ] **Testar em staging** antes da produção
- [ ] **Documentar exceções** e dados não mapeados
- [ ] **Criar plano de rollback** detalhado

---

**Documento criado por:** Everton Oliveira + Claude IA  
**Última atualização:** 22/07/2026  
**Status:** Pronto para implementação de scripts

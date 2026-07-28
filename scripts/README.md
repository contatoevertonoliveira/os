# Scripts de Migração JumperFour → Odoo

Conjunto de scripts Python para migração de dados de produção do JumperFour para Odoo.

## 📋 Estrutura

```
scripts/
├── __init__.py                 # Package init
├── migration_config.py         # Configuração compartilhada
├── odoo_client.py             # Cliente Odoo reutilizável
├── 01_migrate_users.py        # Usuários & Roles (CRÍTICO)
├── 02_migrate_clients.py      # Clientes & Contatos (CRÍTICO)
├── 03_migrate_equipment.py    # Equipamentos & Categorias
├── 04_migrate_tickets.py      # Ordens de Serviço (CRÍTICO)
├── 05_migrate_optional.py     # Chat IA, Checklists, etc
└── README.md                  # Este arquivo
```

## ⚙️ Pré-requisitos

### 1. Odoo Community 17 Instalado
```bash
# Verificar saúde
curl http://localhost:8069/web/health
# Esperado: {"status": "ok"}
```

### 2. Variáveis de Ambiente (.env)
```
ODOO_URL=http://localhost:8069
ODOO_DB=jumperfour
ODOO_USER=admin
ODOO_PASSWORD=sua_senha
ODOO_API_TOKEN=seu_token (opcional)
```

### 3. Dependências Python
```bash
pip install -r requirements.txt  # No projeto JumperFour
```

## 🚀 Execução

### Modo Dry-Run (Recomendado Primeiro)
```bash
# Testar sem fazer mudanças
cd scripts/

python 01_migrate_users.py --dry-run
python 02_migrate_clients.py --dry-run --batch-size 5
python 03_migrate_equipment.py --dry-run
python 04_migrate_tickets.py --dry-run --batch-size 10
python 05_migrate_optional.py --dry-run
```

### Migração Real
```bash
# Execução completa (em ordem)
python 01_migrate_users.py
python 02_migrate_clients.py
python 03_migrate_equipment.py
python 04_migrate_tickets.py
python 05_migrate_optional.py
```

## 📊 Scripts Disponíveis

### 01_migrate_users.py (⭐ CRÍTICO)
**Modelos:** User, UserProfile, RoleLevel  
**Registros:** 24 total (9 usuários + 6 roles + 9 profiles)

```bash
python 01_migrate_users.py --dry-run
python 01_migrate_users.py --skip-roles  # Pular roles se já existem
```

**O que faz:**
- RoleLevel → res.groups
- User → res.users
- UserProfile → hr.employee

---

### 02_migrate_clients.py (⭐ CRÍTICO)
**Modelos:** Client, ClientHub, ContactClient  
**Registros:** 344 total (20 clientes + 53 hubs + 131 contatos)

```bash
python 02_migrate_clients.py --dry-run
python 02_migrate_clients.py --batch-size 10
```

**O que faz:**
- Client → res.partner (is_company=True)
- ClientHub → res.partner (child)
- ContactClient → res.partner (contact)

**Batch Processing:**
- Clientes: 1 de cada vez (sem I/O pesado)
- Hubs: 10 por lote
- Contatos: 10 por lote (131 registros = 14 batches)

---

### 03_migrate_equipment.py (🟡 IMPORTANTE)
**Modelos:** Equipment, EquipmentType, OrderType, ProblemType, System, TicketType  
**Registros:** 49 total

```bash
python 03_migrate_equipment.py --dry-run
```

**O que faz:**
- Equipment → product.product (type="service")
- ProblemType → helpdesk.ticket.category
- System → helpdesk.ticket.tag
- OrderType, TicketType → campos customizados

---

### 04_migrate_tickets.py (⭐ CRÍTICO)
**Modelos:** Ticket, TicketStatus, TicketImage, TicketUpdate  
**Registros:** 578 total (257 tickets + 128 imagens + 186 updates)

```bash
python 04_migrate_tickets.py --dry-run
python 04_migrate_tickets.py --batch-size 20  # Pequeno por ser crítico
```

**⚠️ MAIOR VOLUME - Requer batch processing!**

**O que faz:**
- TicketStatus → helpdesk.ticket.stage
- Ticket → helpdesk.ticket
- TicketImage → ir.attachment (uploads)
- TicketUpdate → mail.message

---

### 05_migrate_optional.py (🟡 OPCIONAL)
**Modelos:** AIChatSession, PrivateChatThread, DailyChecklist, ShiftHandover  
**Registros:** 150+ total

```bash
python 05_migrate_optional.py --dry-run
python 05_migrate_optional.py --skip-chat --skip-checklist
```

**O que faz:**
- AIChatSession → Manter em Django (não mapeia bem)
- PrivateChatThread → mail.activity (ou Django)
- DailyChecklist → helpdesk.sla (ou Django custom)
- ShiftHandover → Custom Odoo module

---

## 📊 Tempos Estimados (com batch processing)

| Script | Registros | Tempo Est. |
|--------|-----------|-----------|
| 01_users | 24 | 2-3 min |
| 02_clients | 344 | 10-15 min |
| 03_equipment | 49 | 2-3 min |
| 04_tickets | 578 | **20-30 min** ⚠️ |
| 05_optional | 150+ | 5-10 min |
| **TOTAL** | **1,441** | **40-60 min** |

## 🔍 Verificação

### Verificar Odoo Após Migração
```bash
# Usuários
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8069/api/resource/res.users?limit=1

# Clientes
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8069/api/resource/res.partner?limit=1

# Tickets
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8069/api/resource/helpdesk.ticket?limit=1
```

## 📝 Logs

Todos os scripts geram logs em:
```
logs/migration/migration_YYYYMMDD_HHMMSS.log
```

**Exemplo:**
```
2026-07-22 10:34:16 - 01_migrate_users - INFO - ✅ Usuário criado: admin
2026-07-22 10:34:17 - 01_migrate_users - INFO - ⏭️  Usuário já existe: operator
```

## ⚠️ Troubleshooting

### Erro: "Odoo não está acessível"
```bash
# Verificar se Odoo está rodando
curl http://localhost:8069/web/health
# Se responder {"status": "ok"}, está ok
```

### Erro: "Batch timeout"
```python
# Aumentar timeout em migration_config.py
MIGRATION_CONFIG['timeout_per_batch'] = 60  # 60 segundos

# Ou reduzir batch size
python 04_migrate_tickets.py --batch-size 10
```

### Erro: "Usuário não tem permissão"
```bash
# Verificar credenciais do Odoo admin
ODOO_USER=admin
ODOO_PASSWORD=sua_senha_correta
```

## 🔄 Rollback

Se houver erro, os dados NÃO foram modificados no JumperFour (apenas lido).

Para rollback no Odoo:
1. Restaurar backup de BD Odoo antes da migração
2. Limpar registros criados manualmente se necessário

## 📈 Performance Tuning

### Para Migração Mais Rápida
```python
# migration_config.py
MIGRATION_CONFIG = {
    'batch_size_tickets': 50,      # Aumentar (com cuidado!)
    'batch_delay': 0.1,            # Diminuir
    'timeout_per_batch': 60,       # Aumentar se der timeout
}
```

### Para Mais Segurança
```python
# migration_config.py
MIGRATION_CONFIG = {
    'batch_size_tickets': 5,       # Diminuir
    'batch_delay': 2.0,            # Aumentar
    'timeout_per_batch': 120,      # Aumentar
}
```

## ✅ Checklist de Execução

- [ ] Backup completo do Odoo (antes de começar)
- [ ] Verificar conexão: `curl http://localhost:8069/web/health`
- [ ] Testar 01_users em dry-run
- [ ] Testar 02_clients em dry-run
- [ ] Executar 01_users (real)
- [ ] Executar 02_clients (real)
- [ ] Executar 03_equipment (real)
- [ ] Executar 04_tickets (real, com cuidado!)
- [ ] Executar 05_optional (real)
- [ ] Validar dados em Odoo
- [ ] Monitorar logs para erros

## 📞 Suporte

Para dúvidas ou erros:
1. Verificar `logs/migration/migration_*.log`
2. Revisar `migration_config.py` para ajustes
3. Testar em dry-run antes de real
4. Consultar `COMPARISON_ANALYSIS.md` para contexto

---

**Versão:** 1.0  
**Data:** 22/07/2026  
**Status:** Pronto para execução

"""
Configuração compartilhada para scripts de migração
"""
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ==================== CONFIGURAÇÃO ODOO ====================
ODOO_CONFIG = {
    'url': os.getenv('ODOO_URL', 'http://localhost:8069'),
    'db': os.getenv('ODOO_DB', 'jumperfour'),
    'username': os.getenv('ODOO_USER', 'admin'),
    'password': os.getenv('ODOO_PASSWORD', 'admin'),
    'token': os.getenv('ODOO_API_TOKEN', ''),
}

# ==================== CONFIGURAÇÃO DE MIGRAÇÃO ====================
MIGRATION_CONFIG = {
    'batch_size_users': 5,           # Usuários (sem I/O pesado)
    'batch_size_clients': 10,        # Clientes/parceiros
    'batch_size_equipment': 10,      # Equipamentos
    'batch_size_tickets': 20,        # Tickets (batch pequeno por ser crítico)
    'batch_size_images': 5,          # Imagens (I/O pesado, batch pequeno)
    'batch_size_updates': 25,        # Updates
    'batch_size_chat': 50,           # Chat (menos crítico)
    'batch_delay': 0.5,              # Delay entre batches (segundos)
    'timeout_per_batch': 30,         # Timeout por batch (segundos)
}

# ==================== LOGGING ====================
LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs', 'migration')
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = os.path.join(LOG_DIR, f'migration_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# ==================== CONSTANTES ====================
SKIP_MODELS = {
    'EquipmentType',      # Vazio
    'TechnicianTravel',   # Vazio
    'TravelSegment',      # Vazio
    'ChecklistTemplate',  # Vazio
    'TicketFavorite',     # Vazio
}

NOTIFICATION_CLEANUP_DAYS = 180  # Descartar notificações > 180 dias

# ==================== STATUS CÓDIGOS ====================
SUCCESS = 'success'
ERROR = 'error'
SKIPPED = 'skipped'
PARTIAL = 'partial'

# ==================== MAPPING CONSTANTES ====================
ROLE_MAPPING = {
    'super_admin': 'system',
    'admin': 'admin',
    'technician': 'technician',
    'operator': 'operator',
    'standard': 'user',
}

PRIORITY_MAPPING = {
    'low': '1',
    'medium': '2',
    'high': '3',
    'urgent': '4',
}

def get_logger(name):
    """Get logger para um módulo específico"""
    return logging.getLogger(name)

def log_migration_start(script_name, model_name, count):
    """Log início de migração"""
    logger = get_logger(script_name)
    logger.info(f"{'='*80}")
    logger.info(f"INICIANDO MIGRAÇÃO: {model_name}")
    logger.info(f"Total de registros: {count}")
    logger.info(f"{'='*80}\n")

def log_migration_end(script_name, model_name, success, failed, skipped):
    """Log fim de migração"""
    logger = get_logger(script_name)
    logger.info(f"\n{'='*80}")
    logger.info(f"MIGRAÇÃO CONCLUÍDA: {model_name}")
    logger.info(f"  ✅ Sucesso: {success}")
    logger.info(f"  ❌ Erros: {failed}")
    logger.info(f"  ⏭️  Pulados: {skipped}")
    logger.info(f"{'='*80}\n")

def log_batch(script_name, batch_num, batch_size, status):
    """Log de batch"""
    logger = get_logger(script_name)
    logger.debug(f"Batch #{batch_num} ({batch_size} registros): {status}")

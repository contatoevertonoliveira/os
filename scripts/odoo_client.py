"""
Cliente Odoo para migração - wrapper da API nativa XML-RPC (xmlrpc/2/common e xmlrpc/2/object)
"""
import time
import logging
import xmlrpc.client
from typing import Dict, List, Optional, Any
from migration_config import ODOO_CONFIG, MIGRATION_CONFIG

logger = logging.getLogger(__name__)


class OdooMigrationClient:
    """Cliente para integração com Odoo durante migração (via XML-RPC nativo)"""

    def __init__(self):
        self.base_url = ODOO_CONFIG['url'].rstrip('/')
        self.db = ODOO_CONFIG['db']
        self.username = ODOO_CONFIG['username']
        self.password = ODOO_CONFIG['password']
        self.timeout = MIGRATION_CONFIG['timeout_per_batch']
        self.batch_delay = MIGRATION_CONFIG['batch_delay']

        self._common = xmlrpc.client.ServerProxy(f"{self.base_url}/xmlrpc/2/common")
        self._models = xmlrpc.client.ServerProxy(f"{self.base_url}/xmlrpc/2/object")
        self._uid = None

    def _authenticate(self) -> int:
        """Autentica e retorna o uid (cacheado após a primeira chamada)"""
        if self._uid is None:
            self._uid = self._common.authenticate(self.db, self.username, self.password, {})
            if not self._uid:
                raise ConnectionError(
                    f"Falha na autenticação Odoo (db={self.db}, user={self.username}). "
                    "Verifique ODOO_DB/ODOO_USER/ODOO_PASSWORD no .env"
                )
        return self._uid

    def _execute(self, model: str, method: str, *args, **kwargs):
        """Chama execute_kw no endpoint /xmlrpc/2/object"""
        uid = self._authenticate()
        return self._models.execute_kw(
            self.db, uid, self.password, model, method, list(args), kwargs
        )

    def health_check(self) -> bool:
        """Verifica se Odoo está acessível e a autenticação funciona"""
        try:
            version = self._common.version()
            uid = self._authenticate()
            is_healthy = bool(version) and bool(uid)
            logger.info(f"Health check Odoo: {'✅ OK' if is_healthy else '❌ FALHOU'} (uid={uid})")
            return is_healthy
        except Exception as e:
            logger.error(f"Health check falhou: {e}")
            return False

    def create_record(self, model: str, data: Dict[str, Any]) -> Optional[Dict]:
        """Cria um registro. Retorna {'id': novo_id} para compatibilidade com o código chamador."""
        try:
            new_id = self._execute(model, 'create', data)
            return {'id': new_id} if new_id else None
        except Exception as e:
            logger.error(f"Erro ao criar {model}: {e}")
            raise

    def create_batch(self, model: str, records: List[Dict[str, Any]],
                    batch_size: Optional[int] = None) -> Dict[str, Any]:
        """Cria múltiplos registros em batches"""
        if batch_size is None:
            batch_size = MIGRATION_CONFIG.get(f'batch_size_{model.lower()}', 10)

        success_count = 0
        error_count = 0
        error_details = []

        total_batches = (len(records) + batch_size - 1) // batch_size

        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(records))
            batch = records[start_idx:end_idx]

            try:
                for record in batch:
                    try:
                        result = self.create_record(model, record)
                        if result:
                            success_count += 1
                        else:
                            error_count += 1
                            error_details.append(f"Resposta nula para: {record.get('name', record)}")
                    except Exception as e:
                        error_count += 1
                        error_details.append(f"{record.get('name', record)}: {str(e)}")

                logger.debug(f"Batch {batch_num + 1}/{total_batches} concluído: {success_count} sucesso, {error_count} erros")

                if batch_num < total_batches - 1:
                    time.sleep(self.batch_delay)

            except Exception as e:
                logger.error(f"Erro ao processar batch {batch_num + 1}: {e}")
                error_count += len(batch)
                error_details.append(f"Batch inteiro falhou: {str(e)}")

        return {
            'total': len(records),
            'success': success_count,
            'error': error_count,
            'error_details': error_details[:10],
        }

    def update_record(self, model: str, record_id: int, data: Dict[str, Any]) -> Optional[Dict]:
        """Atualiza um registro"""
        try:
            ok = self._execute(model, 'write', [record_id], data)
            return {'id': record_id} if ok else None
        except Exception as e:
            logger.error(f"Erro ao atualizar {model}/{record_id}: {e}")
            raise

    def search_records(self, model: str, filters: Optional[List] = None,
                     limit: int = 100, fields: Optional[List] = None) -> List[Dict]:
        """Busca registros com filtros (domain no formato Odoo, ex: [('code', '=', 'x')])"""
        try:
            domain = filters or []
            kwargs = {'limit': limit}
            if fields:
                kwargs['fields'] = fields
            else:
                kwargs['fields'] = ['id', 'name']
            return self._execute(model, 'search_read', domain, **kwargs)
        except Exception as e:
            logger.error(f"Erro ao buscar {model}: {e}")
            return []

    def get_record(self, model: str, record_id: int, fields: Optional[List] = None) -> Optional[Dict]:
        """Busca um registro específico"""
        try:
            kwargs = {'fields': fields} if fields else {}
            result = self._execute(model, 'read', [record_id], **kwargs)
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Erro ao buscar {model}/{record_id}: {e}")
            return None

    def record_exists(self, model: str, filters: List) -> bool:
        """Verifica se um registro existe"""
        try:
            results = self.search_records(model, filters=filters, limit=1)
            return len(results) > 0
        except Exception:
            return False

    def get_or_create(self, model: str, search_filters: List,
                     create_data: Dict[str, Any]) -> Optional[Dict]:
        """Busca um registro ou cria um novo se não existir"""
        try:
            existing = self.search_records(model, filters=search_filters, limit=1)
            if existing:
                logger.debug(f"Registro {model} já existe: {existing[0].get('id')}")
                return existing[0]

            logger.debug(f"Criando novo {model}")
            result = self.create_record(model, create_data)
            return result

        except Exception as e:
            logger.error(f"Erro em get_or_create {model}: {e}")
            raise

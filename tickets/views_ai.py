"""
Views do Chat IA — endpoints para o widget de chat inteligente.
"""
import json
import re
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone

from .models import SystemSettings, AIChatSession, AIChatMessage, AIUserMemory
from .ai_service import run_agent
from .ai_tools import TOOL_DEFINITIONS, SYSTEM_PROMPT, execute_tool

CLEAR_CHAT_CONFIRMATION = "Histórico limpo! 🧹 Começamos do zero. Como posso ajudar?"

# Detecta pedidos explícitos de "limpar o chat" antes de chamar o modelo — o
# modelo às vezes apenas repete o texto de confirmação sem de fato chamar a
# tool clear_chat, o que deixava o histórico intacto no servidor.
_CLEAR_CHAT_RE = re.compile(
    r'\b(limp\w*|apag\w*|reset\w*)\b.{0,12}\b(chat|conversa|hist[oó]ric\w*)\b'
    r'|\blimp\w*\s+tudo\b'
    r'|\bnovo\s+chat\b',
    re.IGNORECASE
)


def _is_clear_chat_request(text):
    return bool(_CLEAR_CHAT_RE.search(text))


def _get_settings():
    obj, _ = SystemSettings.objects.get_or_create(pk=1)
    return obj


class AIChatView(LoginRequiredMixin, View):
    """POST /ai/chat/ — envia mensagem e recebe resposta da IA."""

    def post(self, request):
        settings_obj = _get_settings()
        if not settings_obj.ai_enabled:
            return JsonResponse({"ok": False, "error": "Assistente de IA não está ativado."}, status=403)

        # Verifica se o usuário tem permissão para acessar o chat IA.
        # Super Admin sempre tem acesso, independente do valor salvo no profile.
        user_profile = getattr(request.user, 'profile', None)
        is_super_admin = user_profile and user_profile.role == 'super_admin'
        if user_profile and not user_profile.ai_chat_enabled and not is_super_admin:
            return JsonResponse({"ok": False, "error": "Você não tem permissão para usar o Chat IA."}, status=403)

        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "JSON inválido."}, status=400)

        user_message = (body.get("message") or "").strip()
        session_id = body.get("session_id")
        is_proactive_check = bool(body.get("proactive_check"))

        if not user_message and not is_proactive_check:
            return JsonResponse({"ok": False, "error": "Mensagem vazia."}, status=400)

        if not is_proactive_check and _is_clear_chat_request(user_message):
            AIChatSession.objects.filter(user=request.user).delete()
            new_session = AIChatSession.objects.create(user=request.user, title="Nova conversa")
            AIChatMessage.objects.create(session=new_session, role='assistant', content=CLEAR_CHAT_CONFIRMATION)
            return JsonResponse({
                "ok": True,
                "session_id": new_session.id,
                "response": CLEAR_CHAT_CONFIRMATION,
                "clear_chat": True,
                "new_ticket_id": None,
                "new_ticket_formatted_id": None,
            })

        # Obtém ou cria sessão
        session = None
        if session_id:
            try:
                session = AIChatSession.objects.get(pk=session_id, user=request.user)
            except AIChatSession.DoesNotExist:
                pass

        if not session:
            session = AIChatSession.objects.create(
                user=request.user,
                title=user_message[:80] if user_message else "Nova conversa",
            )

        # Salva mensagem do usuário — a verificação proativa (login) é disparada pelo
        # sistema, não pelo usuário, então não vira uma mensagem no histórico visível.
        if not is_proactive_check:
            AIChatMessage.objects.create(session=session, role='user', content=user_message)

        # Monta histórico para enviar ao modelo (últimas 20 mensagens para não estourar contexto)
        history = list(
            session.messages.order_by('created_at').values('role', 'content')
        )
        # Remove mensagens de role 'tool' do histórico visível — são internas
        visible_history = [m for m in history if m['role'] in ('user', 'assistant')]

        first_name = (request.user.first_name or request.user.username).split()[0]
        is_new_conversation = len(visible_history) <= 1
        current_hour = timezone.localtime(timezone.now()).hour

        memory = AIUserMemory.objects.filter(user=request.user).first()
        memory_notes = (memory.notes.strip() if memory else "")

        system_with_user = (
            SYSTEM_PROMPT
            + f"\n\nUSUÁRIO ATUAL: {first_name}. Use o primeiro nome dele ocasionalmente para tornar a conversa mais natural — não em todas as mensagens, apenas em perguntas, confirmações ou quando fizer sentido humanizar."
            + (f"\n\nMEMÓRIA SOBRE ESTE USUÁRIO (aprendida em conversas anteriores):\n{memory_notes}" if memory_notes else "")
            + f"\n\nHORÁRIO ATUAL: {current_hour}h (use para escolher Bom dia/Boa tarde/Boa noite quando for se apresentar)."
            + (
                "\n\nESTA É A PRIMEIRA MENSAGEM DESTA CONVERSA — apresente-se como instruído em IDENTIDADE antes de responder ao pedido do usuário."
                if is_new_conversation
                else "\n\nEsta conversa já está em andamento — NÃO se apresente novamente, apenas responda normalmente."
            )
        )

        messages = [{"role": "system", "content": system_with_user}] + [
            {"role": m["role"], "content": m["content"]}
            for m in visible_history[-20:]
        ]

        if is_proactive_check:
            attempt_number = 1
            if user_profile:
                user_profile.ai_proactive_alert_count = (user_profile.ai_proactive_alert_count or 0) + 1
                user_profile.save(update_fields=['ai_proactive_alert_count'])
                attempt_number = user_profile.ai_proactive_alert_count

            messages.append({
                "role": "user",
                "content": (
                    "[VERIFICAÇÃO AUTOMÁTICA DE PENDÊNCIAS — disparada pelo sistema porque acabei de logar/abrir "
                    f"o chat, não é uma mensagem digitada por mim. Esta é a {attempt_number}ª vez que você me "
                    "aborda sobre essas pendências sem eu ter dado baixa ainda (conte a partir de 1). Chame "
                    "check_pending_alerts e me avise — varie a frase e o tom conforme o número da tentativa: "
                    "na 1ª seja normal e direto; da 2ª em diante, reconheça com leveza/humor que já tinha "
                    "avisado antes (ex: 'de novo, rs'); da 3ª em diante, seja mais insistente mas educado, "
                    "peça desculpas pela insistência e pergunte se já se inteirou do assunto e se pode dar baixa.]"
                ),
            })

        # Executor de tools que injeta o usuário atual; rastreia se clear_chat foi chamado
        # e se alguma tool alterou uma OS (para o front-end saber que precisa
        # atualizar a lista sem esperar um F5 do usuário).
        _clear_requested    = {"value": False}
        _new_ticket         = {"id": None, "formatted_id": None}
        _updated_ticket_id  = {"value": None}
        _list_changed       = {"value": False}
        _open_private_chat  = {"value": None}

        def tool_executor(tool_name, args):
            result = execute_tool(tool_name, args, request.user)
            if result.get("clear_chat"):
                _clear_requested["value"] = True
            data = result.get("data") or {}
            if tool_name == "create_ticket" and result.get("ok"):
                _new_ticket["id"]           = data.get("id")
                _new_ticket["formatted_id"] = data.get("formatted_id")
                _list_changed["value"] = True
            elif tool_name in ("update_ticket", "add_ticket_evolution") and result.get("ok"):
                _updated_ticket_id["value"] = data.get("ticket_id") or data.get("id") or args.get("ticket_id")
                _list_changed["value"] = True
            elif tool_name == "delete_ticket" and result.get("ok"):
                _list_changed["value"] = True
            elif tool_name == "open_private_chat" and result.get("ok"):
                _open_private_chat["value"] = {
                    "thread_id": data.get("thread_id"),
                    "recipient_id": data.get("recipient_id"),
                    "recipient_name": data.get("recipient_name"),
                }
            return result

        # Chama o agente
        response_text = run_agent(settings_obj, messages, TOOL_DEFINITIONS, tool_executor)

        if _clear_requested["value"]:
            # Apaga TODAS as sessões antigas do usuário (incluindo a atual, que
            # já cumpriu seu papel nesta requisição) e começa uma sessão nova
            # em folha — evita gravar na sessão que acabou de ser removida.
            AIChatSession.objects.filter(user=request.user).delete()
            session = AIChatSession.objects.create(user=request.user, title="Nova conversa")
            AIChatMessage.objects.create(session=session, role='assistant', content=response_text)
        else:
            # Salva resposta do assistente
            AIChatMessage.objects.create(session=session, role='assistant', content=response_text)

            # Atualiza título da sessão se for a primeira resposta
            if user_message and session.messages.count() <= 2:
                session.title = user_message[:80]
                session.save(update_fields=['title', 'updated_at'])
            else:
                session.save(update_fields=['updated_at'])

        return JsonResponse({
            "ok": True,
            "session_id": session.id,
            "response": response_text,
            "clear_chat": _clear_requested["value"],
            "new_ticket_id": _new_ticket["id"],
            "new_ticket_formatted_id": _new_ticket["formatted_id"],
            "updated_ticket_id": _updated_ticket_id["value"],
            "ticket_list_changed": _list_changed["value"],
            "open_private_chat": _open_private_chat["value"],
        })


class AIChatProactiveCheckView(LoginRequiredMixin, View):
    """
    GET /ai/chat/proactive-check/ — chamada pelo widget periodicamente (poll leve,
    sem LLM) para decidir se o Jota4 deve abrir sozinho e avisar sobre mensagens
    diretas ou alertas de passagem de turno pendentes.

    Só dispara quando há algo NOVO desde a última vez que avisou nesta sessão
    (comparando os IDs pendentes com os já avisados, guardados na sessão) — assim
    o poll pode rodar a cada ~30s sem custo de tokens, e só aciona o agente (que
    aí sim consome tokens) quando realmente chegou algo novo. Isso cobre tanto o
    caso "acabou de logar" quanto "já estava logado e alguém mandou mensagem agora".

    Quando não há mais nada pendente, o contador de insistência (usado para variar
    o tom do aviso a cada nova tentativa) é zerado, e a sessão esquece os IDs já
    avisados — então uma pendência futura começa do zero.
    """

    def get(self, request):
        settings_obj = _get_settings()
        profile = getattr(request.user, 'profile', None)
        is_super_admin = profile and profile.role == 'super_admin'

        if not settings_obj.ai_enabled or (profile and not profile.ai_chat_enabled and not is_super_admin):
            return JsonResponse({"ok": True, "should_alert": False})

        from .models import Notification, ShiftHandoverEntryAlert

        current_notification_ids = set(
            Notification.objects.filter(
                recipient=request.user, notification_type='message', is_read=False
            ).values_list('id', flat=True)
        )
        current_alert_ids = set(
            ShiftHandoverEntryAlert.objects.filter(
                target_user=request.user, acknowledged_at__isnull=True
            ).values_list('id', flat=True)
        )

        if not current_notification_ids and not current_alert_ids:
            request.session['ai_alerted_notification_ids'] = []
            request.session['ai_alerted_handover_alert_ids'] = []
            if profile and profile.ai_proactive_alert_count:
                profile.ai_proactive_alert_count = 0
                profile.save(update_fields=['ai_proactive_alert_count'])
            return JsonResponse({"ok": True, "should_alert": False})

        already_notification_ids = set(request.session.get('ai_alerted_notification_ids') or [])
        already_alert_ids = set(request.session.get('ai_alerted_handover_alert_ids') or [])

        has_new = bool(current_notification_ids - already_notification_ids) or bool(current_alert_ids - already_alert_ids)
        if not has_new:
            return JsonResponse({"ok": True, "should_alert": False})

        request.session['ai_alerted_notification_ids'] = list(current_notification_ids)
        request.session['ai_alerted_handover_alert_ids'] = list(current_alert_ids)

        return JsonResponse({"ok": True, "should_alert": True})


class AIChatTestView(LoginRequiredMixin, View):
    """POST /ai/chat/test/ — testa a conexão com o provider de IA configurado."""

    def post(self, request):
        role = getattr(getattr(request.user, 'profile', None), 'role', None)
        if role not in ('admin', 'super_admin'):
            return JsonResponse({"ok": False, "error": "Apenas administradores podem testar a conexão."}, status=403)

        try:
            body = json.loads(request.body)
        except Exception:
            body = {}

        # Monta um settings temporário com os dados enviados pelo formulário
        # (permite testar antes de salvar definitivamente)
        from .models import SystemSettings
        settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)

        provider = body.get('provider') or settings_obj.ai_provider
        api_key = body.get('api_key') or settings_obj.ai_api_key
        model = body.get('model') or settings_obj.ai_model

        if not api_key:
            return JsonResponse({"ok": False, "error": "Nenhuma chave de API informada."})

        # Cria um objeto temporário com os dados do teste
        class TempSettings:
            pass

        temp = TempSettings()
        temp.ai_provider = provider
        temp.ai_api_key = api_key
        temp.ai_model = model

        from .ai_service import run_agent

        messages = [
            {"role": "system", "content": "Você é um assistente de teste. Responda apenas: 'Conexão estabelecida com sucesso!'"},
            {"role": "user", "content": "Teste de conexão."},
        ]

        try:
            response = run_agent(temp, messages, [], lambda name, args: {})
            if response and '⚠️' not in response:
                return JsonResponse({"ok": True, "message": response.strip()})
            else:
                return JsonResponse({"ok": False, "error": response or "Sem resposta do modelo."})
        except Exception as e:
            return JsonResponse({"ok": False, "error": str(e)})


class AIChatNewSessionView(LoginRequiredMixin, View):
    """POST /ai/chat/new/ — cria nova sessão de chat."""

    def post(self, request):
        settings_obj = _get_settings()
        if not settings_obj.ai_enabled:
            return JsonResponse({"ok": False, "error": "IA não ativada."}, status=403)

        session = AIChatSession.objects.create(user=request.user, title="Nova conversa")
        return JsonResponse({"ok": True, "session_id": session.id})


class AIChatHistoryView(LoginRequiredMixin, View):
    """GET /ai/chat/history/?session_id=X — retorna histórico de uma sessão."""

    def get(self, request):
        session_id = request.GET.get("session_id")
        if not session_id:
            # Lista sessões recentes do usuário
            sessions = AIChatSession.objects.filter(user=request.user).order_by('-updated_at')[:10]
            return JsonResponse({
                "ok": True,
                "sessions": [{"id": s.id, "title": s.title, "updated_at": s.updated_at.strftime("%d/%m %H:%M")} for s in sessions]
            })

        try:
            session = AIChatSession.objects.get(pk=session_id, user=request.user)
        except AIChatSession.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Sessão não encontrada."}, status=404)

        messages = session.messages.filter(role__in=('user', 'assistant')).order_by('created_at')
        return JsonResponse({
            "ok": True,
            "session_id": session.id,
            "title": session.title,
            "messages": [
                {"role": m.role, "content": m.content, "created_at": m.created_at.strftime("%H:%M")}
                for m in messages
            ]
        })

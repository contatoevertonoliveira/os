"""
Views do Chat Particular — conversas 1:1 entre usuários logados (estilo Messenger),
com o Jota4 podendo ser chamado pelo nome dentro da própria conversa.
"""
import json
import re
from django.contrib.auth.models import User as DjangoUser
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views import View

from .models import (
    ActiveSession, PrivateChatThread, PrivateChatMessage, PrivateChatReadState, SystemSettings,
)
from .ai_service import run_agent
from .ai_tools import TOOL_DEFINITIONS, SYSTEM_PROMPT, execute_tool

# Detecta menções ao robô dentro de uma conversa particular ("Jota4", "jota 4", "J4")
_JOTA4_MENTION_RE = re.compile(r'\bjota\s*4\b|\bj4\b', re.IGNORECASE)

# Tool extra, disponível SÓ dentro de conversas particulares (por isso não faz
# parte do TOOL_DEFINITIONS geral do ai_tools.py — depende da thread em questão).
_CLEAR_PRIVATE_CHAT_TOOL = {
    "name": "clear_private_chat",
    "description": (
        "Limpa o histórico desta conversa particular apenas para quem pediu — a outra "
        "pessoa continua vendo todas as mensagens normalmente, nada é apagado de verdade. "
        "Use SOMENTE quando o usuário pedir explicitamente para limpar/apagar o "
        "chat/histórico desta conversa."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


def _get_thread_for_users(user1, user2):
    a, b = sorted([user1, user2], key=lambda u: u.id)
    thread, _ = PrivateChatThread.objects.get_or_create(user_a=a, user_b=b)
    return thread


def _visible_messages(thread, user, limit):
    """Histórico visível para este usuário — respeita o 'limpar só pra mim'
    (cleared_at), sem afetar o que a outra pessoa enxerga."""
    qs = thread.messages.order_by('created_at')
    read_state = PrivateChatReadState.objects.filter(thread=thread, user=user).first()
    if read_state and read_state.cleared_at:
        qs = qs.filter(created_at__gt=read_state.cleared_at)
    return list(qs[:limit])


def _clear_private_chat_for_user(thread, user):
    read_state, _ = PrivateChatReadState.objects.get_or_create(thread=thread, user=user)
    last_msg = thread.messages.order_by('-created_at').first()
    read_state.cleared_at = timezone.now()
    if last_msg:
        read_state.last_read_message_id = last_msg.id
    read_state.save(update_fields=['cleared_at', 'last_read_message_id'])


def _serialize_message(msg):
    if msg.is_ai_message:
        sender_name = "Jota4"
    else:
        sender_name = (msg.sender.get_full_name() or msg.sender.username) if msg.sender else "?"
    return {
        "id": msg.id,
        "sender_id": msg.sender_id,
        "sender_name": sender_name,
        "is_ai_message": msg.is_ai_message,
        "content": msg.content,
        "created_at": msg.created_at.strftime("%H:%M"),
    }


def _generate_ai_reply(thread, summoned_by):
    """Chama o Jota4 no papel de 'ouvinte' de uma conversa particular — só é
    acionado quando alguém o menciona pelo nome dentro do chat.
    Retorna (mensagem_criada_ou_None, limpou_o_chat: bool)."""
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    if not settings_obj.ai_enabled:
        return None, False

    other = thread.other_user(summoned_by)
    recent = list(thread.messages.order_by('-created_at')[:15])
    recent.reverse()

    def _label(m):
        if m.is_ai_message:
            return "Jota4"
        return (m.sender.get_full_name() or m.sender.username) if m.sender else "?"

    transcript_messages = [
        {"role": "assistant" if m.is_ai_message else "user", "content": f"{_label(m)}: {m.content}"}
        for m in recent
    ]

    system_note = (
        SYSTEM_PROMPT
        + "\n\nCONTEXTO ESPECIAL — CHAT PARTICULAR ENTRE DOIS USUÁRIOS:\n"
        f"Você foi mencionado (chamado pelo nome) dentro de uma conversa particular entre "
        f"{summoned_by.get_full_name() or summoned_by.username} e {other.get_full_name() or other.username}. "
        "Você está apenas ouvindo essa conversa e só participa quando é chamado pelo nome — não tente "
        "conduzir ou dominar o assunto entre os dois, seja breve. Responda como alguém que acabou de ser "
        "chamado, oferecendo ajuda com o que for pedido (pode usar suas ferramentas normalmente se fizer "
        "sentido, atribuindo a ação a quem te chamou). As mensagens abaixo vêm no formato 'Nome: texto' "
        "para você identificar quem disse o quê — não repita esse prefixo na sua resposta.\n"
        "Se quem te chamou pedir para limpar/apagar o histórico desta conversa, use a ferramenta "
        "clear_private_chat — ela só limpa a visão de quem pediu, a outra pessoa continua vendo tudo "
        "normalmente. Como sua resposta aparece para os dois, NÃO diga 'só pra você' (ambíguo para quem "
        f"lê depois) — nomeie quem pediu explicitamente, ex: 'Limpei o histórico para "
        f"{summoned_by.get_full_name() or summoned_by.username} — {other.get_full_name() or other.username} "
        "continua vendo a conversa normalmente.'"
    )

    messages = [{"role": "system", "content": system_note}] + transcript_messages

    _cleared = {"value": False}

    def tool_executor(tool_name, args):
        if tool_name == "clear_private_chat":
            _clear_private_chat_for_user(thread, summoned_by)
            _cleared["value"] = True
            return {"ok": True, "data": {"message": "Histórico limpo para você. A outra pessoa continua vendo a conversa normalmente."}}
        return execute_tool(tool_name, args, summoned_by)

    response_text = run_agent(settings_obj, messages, TOOL_DEFINITIONS + [_CLEAR_PRIVATE_CHAT_TOOL], tool_executor)
    if not response_text:
        return None, _cleared["value"]

    ai_msg = PrivateChatMessage.objects.create(thread=thread, sender=None, is_ai_message=True, content=response_text)
    return ai_msg, _cleared["value"]


class PrivateChatContactsView(LoginRequiredMixin, View):
    """
    GET /chat/private/contacts/ — lista para o painel do ícone do messenger.

    Antes só mostrava colegas ONLINE — se alguém mandasse mensagem e ficasse
    offline antes do destinatário clicar para ver, a lista aparecia vazia e não
    dava pra abrir a conversa pendente de jeito nenhum. Agora sempre mostra:
    - "threads": conversas já existentes (mesmo com a outra pessoa offline),
      com contagem de não lidas e status (online/away/offline), ordenadas com
      as que têm mensagem pendente primeiro;
    - "others": demais colegas online sem conversa iniciada ainda.
    """

    def get(self, request):
        threads = PrivateChatThread.objects.filter(
            Q(user_a=request.user) | Q(user_b=request.user)
        ).select_related('user_a', 'user_b')

        read_states = {
            rs.thread_id: rs.last_read_message_id
            for rs in PrivateChatReadState.objects.filter(thread__in=threads, user=request.user)
        }

        existing_user_ids = set()
        thread_contacts = []
        for thread in threads:
            other = thread.other_user(request.user)
            existing_user_ids.add(other.id)
            last_read = read_states.get(thread.id, 0)
            unread_count = thread.messages.filter(id__gt=last_read).exclude(sender=request.user).count()
            last_msg = thread.messages.order_by('-created_at').first()
            thread_contacts.append({
                "user_id": other.id,
                "name": other.get_full_name() or other.username,
                "status": ActiveSession.get_status(other),
                "thread_id": thread.id,
                "unread_count": unread_count,
                "preview": (last_msg.content or "")[:80] if last_msg else "",
            })
        thread_contacts.sort(key=lambda c: (-c["unread_count"], c["name"].lower()))

        online_ids = set(ActiveSession.online_user_ids())
        others_qs = DjangoUser.objects.filter(
            pk__in=online_ids, is_active=True
        ).exclude(pk=request.user.id).exclude(pk__in=existing_user_ids).order_by('first_name', 'username')
        other_contacts = [{"user_id": u.id, "name": u.get_full_name() or u.username} for u in others_qs]

        return JsonResponse({"ok": True, "data": {"threads": thread_contacts, "others": other_contacts}})


class PrivateChatOpenView(LoginRequiredMixin, View):
    """POST /chat/private/open/ {recipient_id} — abre (ou recupera) a conversa com outro usuário."""

    def post(self, request):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "JSON inválido."}, status=400)

        recipient_id = body.get("recipient_id")
        recipient = DjangoUser.objects.filter(pk=recipient_id, is_active=True).first()
        if not recipient:
            return JsonResponse({"ok": False, "error": "Usuário não encontrado."}, status=404)
        if recipient.id == request.user.id:
            return JsonResponse({"ok": False, "error": "Não é possível abrir um chat consigo mesmo."}, status=400)

        thread = _get_thread_for_users(request.user, recipient)
        messages = _visible_messages(thread, request.user, 50)

        read_state, _ = PrivateChatReadState.objects.get_or_create(thread=thread, user=request.user)
        if messages:
            read_state.last_read_message_id = messages[-1].id
            read_state.save(update_fields=['last_read_message_id'])

        return JsonResponse({"ok": True, "data": {
            "thread_id": thread.id,
            "recipient_id": recipient.id,
            "recipient_name": recipient.get_full_name() or recipient.username,
            "status": ActiveSession.get_status(recipient),
            "messages": [_serialize_message(m) for m in messages],
        }})


class PrivateChatMessagesView(LoginRequiredMixin, View):
    """GET /chat/private/messages/?thread_id=X — histórico e marca como lido para o usuário atual."""

    def get(self, request):
        thread_id = request.GET.get("thread_id")
        try:
            thread = PrivateChatThread.objects.select_related('user_a', 'user_b').get(pk=thread_id)
        except (PrivateChatThread.DoesNotExist, ValueError, TypeError):
            return JsonResponse({"ok": False, "error": "Conversa não encontrada."}, status=404)

        if request.user.id not in (thread.user_a_id, thread.user_b_id):
            return JsonResponse({"ok": False, "error": "Você não participa dessa conversa."}, status=403)

        messages = _visible_messages(thread, request.user, 100)

        read_state, _ = PrivateChatReadState.objects.get_or_create(thread=thread, user=request.user)
        if messages:
            read_state.last_read_message_id = messages[-1].id
            read_state.save(update_fields=['last_read_message_id'])

        other = thread.other_user(request.user)
        return JsonResponse({"ok": True, "data": {
            "thread_id": thread.id,
            "recipient_id": other.id,
            "recipient_name": other.get_full_name() or other.username,
            "status": ActiveSession.get_status(other),
            "messages": [_serialize_message(m) for m in messages],
        }})


class PrivateChatSendView(LoginRequiredMixin, View):
    """
    POST /chat/private/send/ {thread_id, content} — envia mensagem na conversa.
    Se o texto citar "Jota4"/"J4", o robô responde na mesma conversa, visível
    para os dois participantes (modo ouvinte: só fala quando é chamado).
    """

    def post(self, request):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "JSON inválido."}, status=400)

        thread_id = body.get("thread_id")
        content = (body.get("content") or "").strip()
        if not content:
            return JsonResponse({"ok": False, "error": "Mensagem vazia."}, status=400)

        try:
            thread = PrivateChatThread.objects.get(pk=thread_id)
        except (PrivateChatThread.DoesNotExist, ValueError, TypeError):
            return JsonResponse({"ok": False, "error": "Conversa não encontrada."}, status=404)

        if request.user.id not in (thread.user_a_id, thread.user_b_id):
            return JsonResponse({"ok": False, "error": "Você não participa dessa conversa."}, status=403)

        msg = PrivateChatMessage.objects.create(thread=thread, sender=request.user, content=content)
        thread.save(update_fields=['updated_at'])

        read_state, _ = PrivateChatReadState.objects.get_or_create(thread=thread, user=request.user)
        read_state.last_read_message_id = msg.id
        read_state.save(update_fields=['last_read_message_id'])

        new_messages = [msg]
        cleared = False

        if _JOTA4_MENTION_RE.search(content):
            ai_msg, cleared = _generate_ai_reply(thread, request.user)
            if ai_msg:
                new_messages.append(ai_msg)
                # Quem chamou já recebe a resposta nesta mesma chamada — marca como visto pra ele
                read_state.last_read_message_id = ai_msg.id
                read_state.save(update_fields=['last_read_message_id'])

        # Se o Jota4 limpou o histórico, a mensagem que pediu isso (e tudo antes dela)
        # já ficou fora da visão de quem pediu — só devolve a confirmação da IA, para
        # o front-end substituir a conversa exibida em vez de só anexar ao final.
        response_messages = [m for m in new_messages if m.is_ai_message] if cleared else new_messages

        return JsonResponse({"ok": True, "data": {
            "messages": [_serialize_message(m) for m in response_messages],
            "clear_private_chat": cleared,
        }})


class PrivateChatPollView(LoginRequiredMixin, View):
    """
    GET /chat/private/poll/ — poll leve (sem LLM): para cada conversa do usuário,
    informa se há mensagens novas (de outra pessoa ou do Jota4) desde a última vez
    que ele viu, para o front-end decidir se abre/pisca um popup.
    """

    def get(self, request):
        threads = PrivateChatThread.objects.filter(
            Q(user_a=request.user) | Q(user_b=request.user)
        ).select_related('user_a', 'user_b')

        read_states = {
            rs.thread_id: rs.last_read_message_id
            for rs in PrivateChatReadState.objects.filter(thread__in=threads, user=request.user)
        }

        result = []
        for thread in threads:
            last_read = read_states.get(thread.id, 0)
            new_qs = thread.messages.filter(id__gt=last_read).exclude(sender=request.user)
            unread_count = new_qs.count()
            if unread_count == 0:
                continue
            latest = new_qs.order_by('-created_at').first()
            other = thread.other_user(request.user)
            result.append({
                "thread_id": thread.id,
                "other_user_id": other.id,
                "other_user_name": other.get_full_name() or other.username,
                "status": ActiveSession.get_status(other),
                "unread_count": unread_count,
                "preview": (latest.content or "")[:120],
                "is_ai_message": latest.is_ai_message,
            })

        return JsonResponse({"ok": True, "data": result})

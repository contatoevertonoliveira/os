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
from django.views import View

from .models import (
    ActiveSession, PrivateChatThread, PrivateChatMessage, PrivateChatReadState, SystemSettings,
)
from .ai_service import run_agent
from .ai_tools import TOOL_DEFINITIONS, SYSTEM_PROMPT, execute_tool

# Detecta menções ao robô dentro de uma conversa particular ("Jota4", "jota 4", "J4")
_JOTA4_MENTION_RE = re.compile(r'\bjota\s*4\b|\bj4\b', re.IGNORECASE)


def _get_thread_for_users(user1, user2):
    a, b = sorted([user1, user2], key=lambda u: u.id)
    thread, _ = PrivateChatThread.objects.get_or_create(user_a=a, user_b=b)
    return thread


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
    acionado quando alguém o menciona pelo nome dentro do chat."""
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    if not settings_obj.ai_enabled:
        return None

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
        "para você identificar quem disse o quê — não repita esse prefixo na sua resposta."
    )

    messages = [{"role": "system", "content": system_note}] + transcript_messages

    def tool_executor(tool_name, args):
        return execute_tool(tool_name, args, summoned_by)

    response_text = run_agent(settings_obj, messages, TOOL_DEFINITIONS, tool_executor)
    if not response_text:
        return None

    return PrivateChatMessage.objects.create(thread=thread, sender=None, is_ai_message=True, content=response_text)


class PrivateChatOnlineUsersView(LoginRequiredMixin, View):
    """GET /chat/private/online-users/ — colegas atualmente logados, para iniciar um chat novo."""

    def get(self, request):
        online_user_ids = list(ActiveSession.online_user_ids())
        users = DjangoUser.objects.filter(
            pk__in=online_user_ids, is_active=True
        ).exclude(pk=request.user.id).order_by('first_name', 'username')
        return JsonResponse({"ok": True, "data": [
            {"id": u.id, "name": u.get_full_name() or u.username}
            for u in users
        ]})


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
        messages = list(thread.messages.order_by('created_at')[:50])

        read_state, _ = PrivateChatReadState.objects.get_or_create(thread=thread, user=request.user)
        if messages:
            read_state.last_read_message_id = messages[-1].id
            read_state.save(update_fields=['last_read_message_id'])

        is_online = ActiveSession.is_user_online(recipient)

        return JsonResponse({"ok": True, "data": {
            "thread_id": thread.id,
            "recipient_id": recipient.id,
            "recipient_name": recipient.get_full_name() or recipient.username,
            "is_online": is_online,
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

        messages = list(thread.messages.order_by('created_at')[:100])

        read_state, _ = PrivateChatReadState.objects.get_or_create(thread=thread, user=request.user)
        if messages:
            read_state.last_read_message_id = messages[-1].id
            read_state.save(update_fields=['last_read_message_id'])

        other = thread.other_user(request.user)
        return JsonResponse({"ok": True, "data": {
            "thread_id": thread.id,
            "recipient_id": other.id,
            "recipient_name": other.get_full_name() or other.username,
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

        if _JOTA4_MENTION_RE.search(content):
            ai_msg = _generate_ai_reply(thread, request.user)
            if ai_msg:
                new_messages.append(ai_msg)
                # Quem chamou já recebe a resposta nesta mesma chamada — marca como visto pra ele
                read_state.last_read_message_id = ai_msg.id
                read_state.save(update_fields=['last_read_message_id'])

        return JsonResponse({"ok": True, "data": {
            "messages": [_serialize_message(m) for m in new_messages],
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
                "unread_count": unread_count,
                "preview": (latest.content or "")[:120],
                "is_ai_message": latest.is_ai_message,
            })

        return JsonResponse({"ok": True, "data": result})

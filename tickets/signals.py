from django.db.models.signals import m2m_changed, post_save
from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Ticket, Notification, UserProfile, ActiveSession

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Cria automaticamente um UserProfile quando um novo User é criado.
    Garante que todo usuário tenha um profile com ai_chat_enabled = True por padrão.
    """
    if created:
        if not hasattr(instance, 'profile') or instance.profile is None:
            UserProfile.objects.get_or_create(user=instance)

@receiver(m2m_changed, sender=Ticket.technicians.through)
def notify_technician_assignment(sender, instance, action, reverse, model, pk_set, **kwargs):
    """
    Envia notificação quando um técnico é atribuído a um ticket.
    """
    if action == "post_add" and not reverse:
        # instance é o Ticket
        # pk_set contém os IDs dos usuários adicionados
        # model é o modelo User

        for user_id in pk_set:
            try:
                user = model.objects.get(pk=user_id)

                requester_name = instance.requester.get_full_name() or instance.requester.username if instance.requester else "Sistema"
                client_name = instance.client.name if instance.client else "N/A"

                Notification.objects.create(
                    recipient=user,
                    sender=instance.requester,
                    title=f"Nova Missão: OS #{instance.formatted_id}",
                    message=f"Você foi designado para a OS #{instance.formatted_id} - {client_name}.\nSolicitada por: {requester_name}.",
                    notification_type='assignment',
                    related_ticket=instance
                )
            except model.DoesNotExist:
                continue


@receiver(user_logged_out)
def cleanup_active_session_on_logout(sender, request, user, **kwargs):
    """
    Remove o registro de ActiveSession assim que o usuário desloga, para que
    listas de "quem está online" (chat particular, painel admin) parem de
    considerá-lo online imediatamente.

    Usa 'user' (não request.session.session_key) porque no momento em que este
    signal dispara, django.contrib.auth.logout() já deu flush()/cycle_key() na
    sessão — a session_key original já não está mais acessível em request.session.
    Como o sistema já garante 1 sessão ativa por usuário (SingleSessionPerIpMiddleware),
    filtrar por user é seguro e resolve o problema sem depender do timing do signal.
    """
    if user is not None:
        ActiveSession.objects.filter(user=user).delete()

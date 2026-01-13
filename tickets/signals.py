from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Ticket, Notification

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

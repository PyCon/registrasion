from django.db.models.signals import post_save
from django.dispatch import receiver

from registrasion.contrib.mail import send_email
from registrasion.models.commerce import CreditNoteRefund


@receiver(post_save)
def process_refund(sender, instance, created, **kwargs):
    if not issubclass(sender, CreditNoteRefund):
        return
    if created:
        # send refund processed notification
        send_email(
            [instance.parent.invoice.user.email],
            "refund_processed",
            context={
                "amount": -instance.parent.amount,
                "refund": instance,
                "credit_note": instance.parent,
            },
        )

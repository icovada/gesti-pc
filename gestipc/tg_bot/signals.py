from django.db.models.signals import post_save
from django.dispatch import receiver
from tg_bot.bot import bot
from warehouse.models import Loan

from . import processors


@receiver(post_save, sender=Loan)
def notify_loan_user(sender, instance: Loan, created: bool, **kwargs):
    if not created:
        return

    if instance.fkuser.profile.telegram_user is not None:
        message = processors.new_item_loaned_to_user(
            bot, tg_user=instance.fkuser.profile.telegram_user, instance=instance
        )

        instance.notification_message = message.get_message_id()
        instance.save()

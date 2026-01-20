import asyncio
import logging

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from telegram import Bot

from .models import Servizio

logger = logging.getLogger(__name__)


async def _send_poll(servizio_nome, servizio_data_ora):
    """Send a native Telegram poll to the configured group chat. Returns (poll_id, message_id)."""
    chat_id = getattr(settings, "TELEGRAM_SURVEY_CHAT_ID", None)
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)

    if not chat_id:
        logger.warning("TELEGRAM_SURVEY_CHAT_ID not configured, skipping poll")
        return None, None

    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not configured, skipping poll")
        return None, None

    bot = Bot(token=token)

    async with bot:
        message = await bot.send_poll(
            chat_id=chat_id,
            question=f"📢 {servizio_nome} - {servizio_data_ora:%d/%m/%Y %H:%M}\nSei disponibile?",
            options=["✅ Sì", "❌ No", "🤔 Forse"],
            is_anonymous=False,
            allows_multiple_answers=False,
        )

    return message.poll.id, message.message_id


def send_availability_poll(servizio: Servizio) -> None:
    """Send availability poll and update the servizio with poll info."""
    if servizio.poll_id:
        logger.info(f"Servizio {servizio.pkid} already has poll_id, skipping")
        return

    # Send the poll (async)
    poll_id, message_id = asyncio.run(_send_poll(servizio.nome, servizio.data_ora))

    if poll_id:
        # Update the database after the async call completes
        Servizio.objects.filter(pk=servizio.pkid).update(
            poll_id=poll_id,
            poll_message_id=message_id,
        )
        logger.info(
            f"Created poll {poll_id} (message_id={message_id}) "
            f"for servizio {servizio.pkid}"
        )


@receiver(post_save, sender=Servizio)
def servizio_created(sender, instance, created, **kwargs):
    """Send availability poll when a new Servizio is created."""
    if created and not instance.poll_id:
        logger.info(f"New servizio created: {instance.nome}, sending poll")
        # Use on_commit to ensure the transaction is complete before sending
        transaction.on_commit(lambda: send_availability_poll(instance))


async def _delete_poll_message(chat_id, message_id):
    """Delete a poll message from Telegram."""
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not configured, cannot delete message")
        return

    bot = Bot(token=token)
    async with bot:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)


def delete_poll_message(message_id: int) -> None:
    """Delete the poll message from Telegram."""
    chat_id = getattr(settings, "TELEGRAM_SURVEY_CHAT_ID", None)
    if not chat_id:
        logger.warning("TELEGRAM_SURVEY_CHAT_ID not configured, cannot delete message")
        return

    try:
        asyncio.run(_delete_poll_message(chat_id, message_id))
        logger.info(f"Deleted poll message {message_id}")
    except Exception as e:
        logger.error(f"Failed to delete poll message {message_id}: {e}")


@receiver(pre_delete, sender=Servizio)
def servizio_deleted(sender, instance, **kwargs):
    """Delete the associated poll message when a Servizio is deleted."""
    if instance.poll_message_id:
        logger.info(f"Servizio {instance.pkid} deleted, removing poll message {instance.poll_message_id}")
        delete_poll_message(instance.poll_message_id)

import asyncio
import logging

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver
from telegram import Bot

from .models import ChecklistItem, ChecklistTemplateItem, ScheduledTask, Servizio

logger = logging.getLogger(__name__)


async def _send_poll(servizio_nome, servizio_data_ora):
    """Send a native Telegram poll to the configured group chat. Returns (poll_id, message_id)."""
    chat_id = getattr(settings, "TELEGRAM_SURVEY_CHAT_ID", None)
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    thread_id = getattr(settings, "TELEGRAM_SURVEY_THREAD_ID", None)

    if not chat_id:
        logger.warning("TELEGRAM_SURVEY_THREAD_ID not configured, skipping poll")
        return None, None

    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not configured, skipping poll")
        return None, None

    bot = Bot(token=token)

    async with bot:
        message = await bot.send_poll(
            chat_id=chat_id,
            message_thread_id=thread_id,
            question=f"📢 {servizio_nome} - {servizio_data_ora:%d/%m/%Y %H:%M}\nSei disponibile?",
            options=["✅ Sì", "❌ No"],
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


# Fields that appear in the poll question; a change to any of them means the
# already-sent poll is now stale and a follow-up update should be posted.
POLL_CONTENT_FIELDS = ("nome", "data_ora")


async def _send_poll_update(text, reply_to_message_id):
    """Post a text message replying to (quoting) an existing poll message."""
    chat_id = getattr(settings, "TELEGRAM_SURVEY_CHAT_ID", None)
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    thread_id = getattr(settings, "TELEGRAM_SURVEY_THREAD_ID", None)

    if not chat_id:
        logger.warning("TELEGRAM_SURVEY_CHAT_ID not configured, skipping poll update")
        return

    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not configured, skipping poll update")
        return

    bot = Bot(token=token)
    async with bot:
        await bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=text,
            reply_to_message_id=reply_to_message_id,
        )


def notify_poll_update(servizio: Servizio, poll_message_id: int) -> None:
    """Post a follow-up quoting the poll message with the servizio's updated details.

    Telegram does not allow editing a poll's question, so rather than re-creating the
    poll (which would discard existing votes) we reply to it announcing the new data.
    """
    if not poll_message_id:
        logger.warning(
            f"Servizio {servizio.pkid} has no poll_message_id, cannot post update"
        )
        return

    text = (
        "✏️ Attenzione, i dettagli sono cambiati:\n"
        f"📢 {servizio.nome} - {servizio.data_ora:%d/%m/%Y %H:%M}"
    )

    try:
        asyncio.run(_send_poll_update(text, poll_message_id))
        logger.info(f"Posted update for servizio {servizio.pkid} poll")
    except Exception as e:
        logger.error(f"Failed to post update for servizio {servizio.pkid}: {e}")


@receiver(pre_save, sender=Servizio)
def pre_servizio_created(sender, instance, **kwargs) -> None:
    """Stash the current DB state on the instance so post_save can compare it."""
    try:
        instance._pre_save_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        instance._pre_save_instance = None


@receiver(post_save, sender=Servizio)
def servizio_created(sender, instance, created, **kwargs):
    """Send the availability poll on creation, or refresh it when the servizio changes."""
    if created:
        if not instance.poll_id and instance.send_message:
            logger.info(f"New servizio created: {instance.nome}, sending poll")
            # Use on_commit to ensure the transaction is complete before sending
            transaction.on_commit(lambda: send_availability_poll(instance))
        return

    previous = getattr(instance, "_pre_save_instance", None)
    if previous is None:
        return

    # send_message was just turned on and no poll exists yet: send a fresh poll.
    if instance.send_message and not previous.send_message and not instance.poll_id:
        logger.info(f"send_message enabled for servizio {instance.pkid}, sending poll")
        transaction.on_commit(lambda: send_availability_poll(instance))
        return

    # Poll content changed while an open poll exists: post a follow-up update.
    content_changed = any(
        getattr(previous, field) != getattr(instance, field)
        for field in POLL_CONTENT_FIELDS
    )
    if instance.poll_id and not instance.poll_closed and content_changed:
        logger.info(f"Servizio {instance.pkid} details changed, posting poll update")
        poll_message_id = instance.poll_message_id
        transaction.on_commit(lambda: notify_poll_update(instance, poll_message_id))


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


@receiver(post_save, sender=ScheduledTask)
def scheduled_task_created(sender, instance, created, **kwargs):
    """Copy checklist template items when a new ScheduledTask is created."""
    if not created:
        return
    if not instance.type_id:
        return

    template_items = ChecklistTemplateItem.objects.filter(
        servizio_type_id=instance.type_id
    ).order_by("ordine")

    checklist_items = [
        ChecklistItem(
            scheduled_task=instance,
            descrizione=t.descrizione,
            ordine=t.ordine,
        )
        for t in template_items
    ]
    if checklist_items:
        ChecklistItem.objects.bulk_create(checklist_items)
        logger.info(
            f"Created {len(checklist_items)} checklist items for "
            f"scheduled task {instance.pkid}"
        )


@receiver(pre_delete, sender=Servizio)
def servizio_deleted(sender, instance, **kwargs):
    """Delete the associated poll message when a Servizio is deleted."""
    if instance.poll_message_id:
        logger.info(
            f"Servizio {instance.pkid} deleted, removing poll message {instance.poll_message_id}"
        )
        delete_poll_message(instance.poll_message_id)

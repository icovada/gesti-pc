from django.core.management.base import BaseCommand

from tg_bot.bot import run_bot


class Command(BaseCommand):
    help = "Avvia il bot Telegram in modalità polling"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Avvio del bot Telegram..."))
        run_bot()

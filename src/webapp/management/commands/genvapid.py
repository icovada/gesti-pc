from cryptography.hazmat.primitives import serialization
from django.core.management.base import BaseCommand
from py_vapid import Vapid01
from py_vapid.utils import b64urlencode


class Command(BaseCommand):
    help = "Genera una coppia di chiavi VAPID per le notifiche Web Push."

    def handle(self, *args, **options):
        vapid = Vapid01()
        vapid.generate_keys()
        private = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
        public = vapid.public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        self.stdout.write(f"VAPID_PUBLIC_KEY={b64urlencode(public)}")
        self.stdout.write(f"VAPID_PRIVATE_KEY={b64urlencode(private)}")
        self.stderr.write(
            "Aggiungi le due righe all'ambiente. Non cambiarle in seguito: "
            "i dispositivi già iscritti smetterebbero di ricevere notifiche."
        )

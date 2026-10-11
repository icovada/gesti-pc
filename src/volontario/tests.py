from django.test import TestCase

from .codicefiscale import CodiceFiscale
from .models import Volontario

VALID_CF = "RSSMRA90A01H501W"
OTHER_CF = "VRDLGU85M01F205P"


class CodiceFiscaleEqualityTests(TestCase):
    def test_value_equality_and_hash(self):
        a, b = CodiceFiscale(VALID_CF), CodiceFiscale(VALID_CF.lower())
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))
        self.assertNotEqual(a, CodiceFiscale(OTHER_CF))
        self.assertEqual(a, VALID_CF)
        self.assertEqual(hash(a), hash(VALID_CF))
        self.assertEqual(len({a, b, VALID_CF}), 1)
        self.assertNotEqual(a, 42)

    def test_model_instances_compare_by_codice_fiscale(self):
        Volontario.objects.create(
            codice_fiscale=VALID_CF, nome="Mario", cognome="Rossi"
        )
        loaded = Volontario.objects.get(pk=VALID_CF)
        again = Volontario.objects.get(pk=VALID_CF)
        self.assertEqual(loaded, again)
        self.assertEqual(len({loaded, again}), 1)
        # An unsaved instance with the same code (pk still a str) matches too.
        self.assertEqual(Volontario(codice_fiscale=VALID_CF), loaded)
        self.assertNotEqual(
            Volontario.objects.create(
                codice_fiscale=OTHER_CF, nome="Luigi", cognome="Verdi"
            ),
            loaded,
        )

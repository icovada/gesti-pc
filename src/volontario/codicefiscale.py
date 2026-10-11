from enum import StrEnum
from datetime import datetime
from codicefiscale import codicefiscale


class SexEnum(StrEnum):
    MALE = "M"
    FEMALE = "F"


class CodiceFiscale:
    cf: str
    sex: SexEnum
    birth_date: datetime
    birth_place: str
    birth_province: str

    def __init__(self, cf: str):
        self.cf = cf.strip().upper()
        decoded = codicefiscale.decode(self.cf)
        self.sex = decoded["gender"]
        self.birth_date = decoded["birthdate"]
        self.birth_place = decoded["birthplace"]["name"]
        self.birth_province = decoded["birthplace"]["province"]

    def __str__(self):
        return self.cf

    def __repr__(self):
        return f"CodiceFiscale('{self.cf}')"

    def __len__(self):
        return 16

    # Uguaglianza per valore: Django confronta e indicizza le istanze di modello
    # (es. Volontario) tramite la chiave primaria, che è un CodiceFiscale.
    # Vale anche contro la stringa del codice (le istanze non ancora salvate
    # hanno la chiave come str); l'hash coincide con quello della stringa.
    def __eq__(self, other):
        if isinstance(other, CodiceFiscale):
            return self.cf == other.cf
        if isinstance(other, str):
            return self.cf == other
        return NotImplemented

    def __hash__(self):
        return hash(self.cf)

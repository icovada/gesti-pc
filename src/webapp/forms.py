from datetime import timedelta

from django import forms
from django.db.models import Q
from django.utils import timezone

from servizio.models import Servizio, Timbratura

# Oltre questo limite le presenze si correggono solo dall'admin.
GIORNI_MODIFICABILI = 60
# Durata massima di una presenza, salvo servizi più lunghi (vedi `durata_massima`).
DURATA_MASSIMA = timedelta(hours=24)
# Una presenza deve cadere attorno all'orario del servizio scelto.
MARGINE_SERVIZIO = timedelta(hours=6)


def finestra_servizio(servizio):
    """Intervallo in cui può cadere una presenza per il servizio."""
    inizio = servizio.data_ora - MARGINE_SERVIZIO
    fine = (servizio.data_ora_fine or servizio.data_ora) + MARGINE_SERVIZIO
    return inizio, fine


def durata_massima(servizio):
    """Un servizio su più giorni si può registrare con un'unica presenza."""
    if servizio is None:
        return DURATA_MASSIMA
    inizio, fine = finestra_servizio(servizio)
    return max(DURATA_MASSIMA, fine - inizio)


def limite_modifica():
    return timezone.now() - timedelta(days=GIORNI_MODIFICABILI)


def servizi_selezionabili():
    now = timezone.now()
    return Servizio.objects.filter(
        data_ora__lte=now, data_ora__gte=limite_modifica()
    ).order_by("-data_ora")


class ServizioChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.nome} — {timezone.localtime(obj.data_ora):%d/%m/%Y %H:%M}"


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%dT%H:%M", **kwargs)


class PresenzaForm(forms.ModelForm):
    """Presenza inserita o corretta dal volontario.

    Le nuove presenze devono essere collegate a un servizio; nella modifica si
    cambiano solo orari e note.
    """

    class Meta:
        model = Timbratura
        fields = ["fkservizio", "clock_in", "clock_out", "notes"]
        labels = {
            "fkservizio": "Servizio",
            "clock_in": "Entrata",
            "clock_out": "Uscita",
            "notes": "Note",
        }
        widgets = {
            "clock_in": DateTimeLocalInput(),
            "clock_out": DateTimeLocalInput(),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, volontario, **kwargs):
        super().__init__(*args, **kwargs)
        self.volontario = volontario
        self.nuova = self.instance._state.adding
        if self.nuova:
            self.instance.fkvolontario = volontario
            # Il modello propone "adesso": qui gli orari vengono dal servizio scelto.
            self.initial["clock_in"] = None

        if self.nuova:
            self.fields["fkservizio"] = ServizioChoiceField(
                queryset=servizi_selezionabili(),
                label="Servizio",
                empty_label="Scegli il servizio…",
            )
        else:
            del self.fields["fkservizio"]

        # L'uscita si può lasciare vuota solo sul turno ancora aperto.
        self.fields["clock_out"].required = not (
            not self.nuova and self.instance.clock_out is None
        )
        for name in ("clock_in", "clock_out"):
            self.fields[name].widget.attrs["max"] = timezone.localtime().strftime(
                "%Y-%m-%dT%H:%M"
            )

    def clean(self):
        data = super().clean()
        clock_in, clock_out = data.get("clock_in"), data.get("clock_out")
        if clock_in is None:
            return data

        now = timezone.now()
        tolleranza = timedelta(minutes=5)
        if clock_in > now + tolleranza or (clock_out and clock_out > now + tolleranza):
            raise forms.ValidationError("Non puoi inserire orari nel futuro.")
        if clock_in < limite_modifica():
            raise forms.ValidationError(
                f"Puoi inserire o correggere solo presenze degli ultimi "
                f"{GIORNI_MODIFICABILI} giorni. Per quelle precedenti rivolgiti a "
                "un responsabile."
            )
        servizio = data.get("fkservizio")
        if clock_out is not None:
            if clock_out <= clock_in:
                self.add_error("clock_out", "L'uscita deve essere dopo l'entrata.")
                return data
            massimo = durata_massima(servizio or self.instance.fkservizio)
            if clock_out - clock_in > massimo:
                ore = int(massimo.total_seconds() // 3600)
                self.add_error("clock_out", f"Questa presenza non può superare {ore} ore.")
                return data

        if servizio is not None:
            inizio, fine = finestra_servizio(servizio)
            if clock_in > fine or (clock_out or clock_in) < inizio:
                iniziato = timezone.localtime(servizio.data_ora)
                raise forms.ValidationError(
                    "Gli orari non corrispondono al servizio scelto "
                    f"(iniziato il {iniziato:%d/%m/%Y alle %H:%M})."
                )

        self._check_overlap(clock_in, clock_out or now)
        return data

    def _check_overlap(self, start, end):
        """Nessuna sovrapposizione con le altre presenze (quelle aperte valgono fino ad ora)."""
        others = Timbratura.objects.filter(
            fkvolontario=self.volontario, clock_in__lt=end
        ).filter(Q(clock_out__gt=start) | Q(clock_out__isnull=True))
        if self.instance.pk:
            others = others.exclude(pk=self.instance.pk)
        conflitto = others.order_by("clock_in").first()
        if conflitto is not None:
            raise forms.ValidationError(
                "Si sovrappone a una presenza già registrata il "
                f"{timezone.localtime(conflitto.clock_in):%d/%m/%Y dalle %H:%M}."
            )

    def save(self, commit=True):
        entry = super().save(commit=False)
        entry.fkvolontario = self.volontario
        if self.nuova:
            entry.inserita_manualmente = True
        else:
            entry.modificata_at = timezone.now()
        if commit:
            entry.save()
        return entry

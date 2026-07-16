"""Client e logica per le allerte meteo del portale AllertaLOM (Regione Lombardia).

L'endpoint ``lista-zone`` restituisce un XML con la previsione oraria del livello di
criticità per la zona omogenea che contiene il comune richiesto. Questo modulo contiene
solo logica pura e I/O di rete: il rilevamento delle variazioni e l'invio dei messaggi
Telegram sono gestiti dal job in :mod:`tg_bot.bot`.
"""

import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from xml.etree import ElementTree

import httpx
from django.utils import timezone

logger = logging.getLogger(__name__)

BASE_URL = "https://www.allertalom.regione.lombardia.it/lista-zone"

# cdTipologiaGis -> nome leggibile del fenomeno.
CATEGORY_NAMES = {
    2: "Neve",
    3: "Incendi boschivi",
    7: "Temporali",
    8: "Vento forte",
    9: "Rischio idrogeologico",
    10: "Rischio idraulico",
}

# cdLivello -> (nome leggibile, emoji). cdLivello -1 = "Nessuna Previsione".
LEVEL_INFO = {
    0: ("Codice VERDE", "🟢"),
    1: ("Codice GIALLO", "🟡"),
    2: ("Codice ARANCIONE", "🟠"),
    3: ("Codice ROSSO", "🔴"),
}


def category_name(categoria: int) -> str:
    """Nome leggibile del fenomeno, o un fallback se sconosciuto."""
    return CATEGORY_NAMES.get(categoria, f"Categoria {categoria}")


def portal_url(categoria: int, cd_istat_comune: str) -> str:
    """URL della pagina AllertaLOM per la categoria e il comune indicati."""
    return f"{BASE_URL}?cdTipologiaGis={categoria}&cdIstatComune={cd_istat_comune}"


def parse_forecast(xml_text: str) -> list[dict]:
    """Converte l'XML di AllertaLOM in una lista di dict (uno per ora di previsione).

    Ogni elemento contiene: ``dt`` (datetime aware UTC), ``cd_livello`` (int),
    ``livello`` (str), ``nome_zona`` (str), ``codice_zona`` (str). Gli item non
    parsabili vengono ignorati.
    """
    root = ElementTree.fromstring(xml_text)
    items = []
    for item in root.findall("item"):
        dt_raw = item.findtext("dtPrevisione")
        cd_raw = item.findtext("cdLivello")
        if dt_raw is None or cd_raw is None:
            continue
        try:
            dt = datetime.fromtimestamp(int(dt_raw) / 1000, tz=dt_timezone.utc)
            cd_livello = int(cd_raw)
        except (ValueError, TypeError):
            continue
        items.append(
            {
                "dt": dt,
                "cd_livello": cd_livello,
                "livello": item.findtext("livello", "") or "",
                "nome_zona": item.findtext("nomeZonaOmogenea", "") or "",
                "codice_zona": item.findtext("codiceZonaOmogenea", "") or "",
            }
        )
    return items


async def fetch_forecast(categoria: int, cd_istat_comune: str) -> list[dict]:
    """Scarica e parsa la previsione per una categoria e un comune.

    Nota TLS: il server AllertaLOM invia solo il certificato foglia (manca l'intermedio
    Actalis) quindi la verifica standard fallisce. L'endpoint è pubblico e in sola
    lettura, perciò disabilitiamo la verifica del certificato.
    """
    params = {"cdTipologiaGis": categoria, "cdIstatComune": cd_istat_comune}
    async with httpx.AsyncClient(verify=False, timeout=20) as client:
        resp = await client.get(BASE_URL, params=params)
        resp.raise_for_status()
    return parse_forecast(resp.text)


def current_alert(
    items: list[dict], now: datetime, horizon_hours: int, min_level: int = 1
) -> dict | None:
    """Livello di allerta "in corso" nella finestra [now-1h, now+horizon_hours].

    Ritorna il dict dell'item col ``cd_livello`` massimo nella finestra (ignorando gli
    item senza previsione, ``cd_livello`` < 0), oppure ``None`` se non ci sono dati.
    La finestra parte da ``now-1h`` per includere il bucket dell'ora corrente.

    Il dict include anche ``segments``: le fasce orarie contigue in cui il livello è
    ``>= min_level``, ciascuna con ``cd_livello``/``livello``/``start``/``end`` (aware
    UTC). Un'allerta può avere gravità variabile (es. giallo → arancione → giallo), quindi
    ogni cambio di livello o interruzione apre un nuovo segmento. ``start``/``end``
    riassumono l'inizio del primo e la fine dell'ultimo segmento (``None`` se nessuno).
    Poiché ogni item è un bucket orario, la fine di un segmento è l'ultimo bucket + 1h.
    """
    window_start = now - timedelta(hours=1)
    window_end = now + timedelta(hours=horizon_hours)
    relevant = [
        i
        for i in items
        if i["cd_livello"] >= 0 and window_start <= i["dt"] <= window_end
    ]
    if not relevant:
        return None

    top = max(relevant, key=lambda i: i["cd_livello"])

    elevated = sorted(
        (i for i in relevant if i["cd_livello"] >= min_level),
        key=lambda i: i["dt"],
    )
    segments: list[dict] = []
    for item in elevated:
        prev = segments[-1] if segments else None
        if (
            prev
            and prev["cd_livello"] == item["cd_livello"]
            and prev["end"] == item["dt"]
        ):
            prev["end"] = item["dt"] + timedelta(hours=1)
        else:
            segments.append(
                {
                    "cd_livello": item["cd_livello"],
                    "livello": item["livello"],
                    "start": item["dt"],
                    "end": item["dt"] + timedelta(hours=1),
                }
            )

    return {
        "cd_livello": top["cd_livello"],
        "livello": top["livello"],
        "nome_zona": top["nome_zona"],
        "codice_zona": top["codice_zona"],
        "start": segments[0]["start"] if segments else None,
        "end": segments[-1]["end"] if segments else None,
        "segments": segments,
    }


def build_message(
    categoria: int, alert: dict, old_level: int, new_level: int, cd_istat_comune: str
) -> str:
    """Costruisce il messaggio Telegram (Markdown) per una variazione di allerta.

    Il testo di intestazione dipende dalla direzione del cambiamento:
    nuova allerta, aggravamento, miglioramento o rientro.
    """
    nome = category_name(categoria)
    livello_nome, livello_emoji = LEVEL_INFO.get(
        new_level, (alert.get("livello", ""), "⚠️")
    )

    if old_level <= 0 < new_level:
        header = f"🚨 *Nuova allerta meteo — {nome}*"
    elif new_level > old_level:
        header = f"⬆️ *Allerta meteo in peggioramento — {nome}*"
    elif new_level <= 0 < old_level:
        header = f"✅ *Rientro allerta meteo — {nome}*"
    else:
        header = f"⬇️ *Allerta meteo in miglioramento — {nome}*"

    segments = alert.get("segments") or []

    lines = [header, ""]
    if new_level <= 0:
        lines.append(f"{livello_emoji} Situazione tornata a *{livello_nome}*.")
    elif len(segments) > 1:
        lines.append(f"{livello_emoji} Livello massimo: *{livello_nome}*")
    else:
        lines.append(f"{livello_emoji} Livello: *{livello_nome}*")

    zona = alert.get("nome_zona") or ""
    codice_zona = alert.get("codice_zona") or ""
    if zona:
        zona_txt = f"📍 Zona: {zona}"
        if codice_zona:
            zona_txt += f" ({codice_zona})"
        lines.append(zona_txt)

    if new_level > 0:
        if len(segments) > 1:
            lines.append("🕒 Evoluzione prevista:")
            for seg in segments:
                seg_nome, seg_emoji = LEVEL_INFO.get(
                    seg["cd_livello"], (seg.get("livello", ""), "⚠️")
                )
                seg_short = seg_nome.replace("Codice ", "").capitalize()
                seg_start = timezone.localtime(seg["start"])
                seg_end = timezone.localtime(seg["end"])
                lines.append(
                    f"{seg_emoji} {seg_short}: {seg_start:%d/%m %H:%M} → {seg_end:%d/%m %H:%M}"
                )
        elif segments:
            seg_start = timezone.localtime(segments[0]["start"])
            seg_end = timezone.localtime(segments[0]["end"])
            lines.append(
                f"🕒 Dal {seg_start:%d/%m ore %H:%M} al {seg_end:%d/%m ore %H:%M}"
            )
        else:
            lines.append("🕒 Valida per le prossime 24 ore.")

    lines.append("")
    lines.append(
        f"🔗 [Dettagli su AllertaLOM]({portal_url(categoria, cd_istat_comune)})"
    )
    return "\n".join(lines)

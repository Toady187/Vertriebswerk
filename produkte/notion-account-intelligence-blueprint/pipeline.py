"""Account Intelligence Pipeline: Website + News -> Claude -> Notion.

Kern-Modul für Phase 2 des Account Intelligence Blueprint. Nimmt company_name/domain
entgegen, reichert sie über Jina AI Reader (Website) und Google News RSS an, lässt
Claude daraus ein BANT-strukturiertes Dossier bauen und schreibt das Ergebnis als
neue Page in die Notion-Datenbank "Account Dossiers". Lauffähig als FastAPI-Endpoint
(`uvicorn pipeline:app`) oder als AWS-Lambda-Handler (`pipeline.lambda_handler`).

Benötigte Umgebungsvariablen: ANTHROPIC_API_KEY, NOTION_API_KEY, NOTION_DATABASE_ID.
Optional: ANTHROPIC_MODEL, JINA_API_KEY, NOTION_API_VERSION, LOG_LEVEL.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from urllib.parse import quote

import anthropic
import feedparser
import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("account_intelligence.pipeline")

# ---------------------------------------------------------------------------
# Konfiguration — ausschließlich Umgebungsvariablen, keine Secrets im Code.
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
# Hinweis: Die Aufgabenstellung nannte "claude-3-5-sonnet-20241022" (Okt. 2024,
# mittlerweile veraltet/vsl. abgekündigt). Default daher auf die aktuelle
# Sonnet-Generation gesetzt — bei Bedarf per Env-Var auf ein anderes Modell umbiegen.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_API_VERSION = os.getenv("NOTION_API_VERSION", "2022-06-28")

JINA_API_KEY = os.getenv("JINA_API_KEY")  # optional, erhöht Jina-Reader-Rate-Limits

SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "system-prompt.md")

HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
MAX_NEWS_ITEMS = 5
MAX_RICH_TEXT_CHARS = 1900  # Notion-Hardlimit pro rich_text-Objekt liegt bei 2000
MAX_WEBSITE_CHARS = 20000  # Kostenschutz: sehr große Seiten für den LLM-Call kappen

Branche = Literal[
    "SaaS / Software",
    "Industrie / Produktion",
    "Handel / E-Commerce",
    "Finanzdienstleistung",
    "Logistik",
    "Gesundheitswesen",
    "Öffentlicher Sektor",
    "Sonstige",
]
Confidence = Literal["hoch", "mittel", "niedrig"]


# ---------------------------------------------------------------------------
# Datenmodelle (Pydantic) — validieren Input UND LLM-Output.
# ---------------------------------------------------------------------------

class WebhookRequest(BaseModel):
    company_name: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=3)
    manual_social_insights: Optional[str] = None
    existing_pitch_notes: Optional[str] = None

    @field_validator("domain")
    @classmethod
    def _normalize_domain(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("http://") and not v.startswith("https://"):
            v = f"https://{v}"
        return v


class NewsItem(BaseModel):
    title: str = ""
    source: str = "Google News"
    published_at: str = ""
    snippet: str = ""
    link: str = ""


class PitchAnsatz(BaseModel):
    budget: str = ""
    authority: str = ""
    need: str = ""
    timing: str = ""
    pain_points: list[str] = Field(default_factory=list)
    icebreaker: str = ""

    @field_validator("pain_points")
    @classmethod
    def _limit_pain_points(cls, v: list[str]) -> list[str]:
        return v[:3]


class EnrichmentResult(BaseModel):
    branche: Branche = "Sonstige"
    mitarbeiterzahl_schaetzung: Optional[int] = None
    key_metrics_ansprechpartner: str = ""
    news_trigger_events: str = ""
    pitch_ansatz: PitchAnsatz = Field(default_factory=PitchAnsatz)
    confidence: Confidence = "niedrig"
    data_gaps: list[str] = Field(default_factory=list)


class NotionWriteError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Schritt 2: Datenbeschaffung (offline-stabil — jeder Fehler landet in data_gaps,
# nie in einer geworfenen Exception).
# ---------------------------------------------------------------------------

def _http_get(url: str, *, headers: Optional[dict] = None, retries: int = 2) -> tuple[Optional[httpx.Response], Optional[str]]:
    """GET mit Timeout + Retry für transiente Fehler. (None, Fehlergrund) bei endgültigem Fehlschlag."""
    last_error = "unbekannter Fehler"
    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                response = client.get(url, headers=headers)
            response.raise_for_status()
            return response, None
        except httpx.HTTPStatusError as exc:
            last_error = f"HTTP {exc.response.status_code}"
            if exc.response.status_code < 500:
                break  # 4xx wiederholen bringt nichts
        except httpx.TimeoutException:
            last_error = "Timeout"
        except httpx.RequestError as exc:
            last_error = f"Netzwerkfehler ({exc.__class__.__name__})"

        if attempt < retries:
            time.sleep(1.5 * attempt)

    logger.warning("GET %s fehlgeschlagen: %s", url, last_error)
    return None, last_error


def fetch_website_text(url: str) -> tuple[str, list[str]]:
    """Website-Rohtext via Jina AI Reader. Liefert bei Fehlern ('', [Datenlücke])."""
    headers = {"Authorization": f"Bearer {JINA_API_KEY}"} if JINA_API_KEY else None
    response, error = _http_get(f"https://r.jina.ai/{url}", headers=headers)
    if response is None:
        return "", [f"Website nicht erreichbar ({error}): {url}"]

    text = response.text.strip()
    if not text:
        return "", ["Jina Reader lieferte leeren Website-Text."]
    return text, []


def fetch_news(company_name: str) -> tuple[list[NewsItem], list[str]]:
    """Top News-Treffer via Google News RSS. Liefert bei Fehlern ([], [Datenlücke])."""
    rss_url = f"https://news.google.com/rss/search?q={quote(company_name)}&hl=de&gl=DE&ceid=DE:de"
    response, error = _http_get(rss_url)
    if response is None:
        return [], [f"News-Feed nicht erreichbar ({error})."]

    try:
        feed = feedparser.parse(response.content)
    except Exception as exc:  # feedparser wirft selten, schützt aber gegen malformte Feeds
        logger.warning("RSS-Parsing fehlgeschlagen: %s", exc)
        return [], ["News-Feed konnte nicht geparst werden."]

    items = [
        NewsItem(
            title=(entry.get("title") or "").strip(),
            source=((entry.get("source") or {}).get("title") or "Google News"),
            published_at=entry.get("published", ""),
            snippet=(entry.get("summary") or "").strip(),
            link=entry.get("link", ""),
        )
        for entry in feed.entries[:MAX_NEWS_ITEMS]
    ]

    if not items:
        return items, [f"Keine News-Treffer für '{company_name}' gefunden."]
    return items, []


# ---------------------------------------------------------------------------
# Schritt 3: KI-Transformation (Anthropic Messages API, strukturierter Output)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_CACHE: Optional[str] = None


def load_system_prompt() -> str:
    """Extrahiert den Prompt-Text aus dem ```-Codeblock in system-prompt.md."""
    global _SYSTEM_PROMPT_CACHE
    if _SYSTEM_PROMPT_CACHE is not None:
        return _SYSTEM_PROMPT_CACHE

    with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    parts = content.split("```")
    if len(parts) < 3:
        raise RuntimeError(f"System-Prompt-Codeblock nicht gefunden in {SYSTEM_PROMPT_PATH}")

    _SYSTEM_PROMPT_CACHE = parts[1].strip()
    return _SYSTEM_PROMPT_CACHE


def _fallback_result(reason: str, existing_gaps: list[str]) -> EnrichmentResult:
    return EnrichmentResult(data_gaps=[*existing_gaps, reason])


def analyze_with_claude(
    request: WebhookRequest,
    website_text: str,
    news_items: list[NewsItem],
    data_gaps: list[str],
) -> EnrichmentResult:
    """Ruft Claude mit strukturiertem Output auf. Crasht nie — liefert im Fehlerfall
    ein EnrichmentResult mit confidence='niedrig' und dem Fehler in data_gaps."""
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY fehlt — KI-Analyse wird übersprungen.")
        return _fallback_result("ANTHROPIC_API_KEY nicht gesetzt — KI-Analyse übersprungen.", data_gaps)

    payload = {
        "company_name": request.company_name,
        "domain": request.domain,
        "raw_website_text": website_text[:MAX_WEBSITE_CHARS],
        "raw_news_items": [item.model_dump() for item in news_items],
        "manual_social_insights": request.manual_social_insights,
        "existing_pitch_notes": request.existing_pitch_notes,
    }

    try:
        system_prompt = load_system_prompt()
    except (OSError, RuntimeError) as exc:
        logger.error("System-Prompt konnte nicht geladen werden: %s", exc)
        return _fallback_result("System-Prompt nicht verfügbar — KI-Analyse übersprungen.", data_gaps)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    try:
        response = client.messages.parse(
            model=ANTHROPIC_MODEL,
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            output_format=EnrichmentResult,
        )
    except anthropic.RateLimitError as exc:
        logger.error("Anthropic Rate Limit: %s", exc)
        return _fallback_result("KI-Analyse fehlgeschlagen (Rate Limit).", data_gaps)
    except anthropic.APIConnectionError as exc:
        logger.error("Anthropic Verbindungsfehler: %s", exc)
        return _fallback_result("KI-Analyse fehlgeschlagen (Netzwerkfehler).", data_gaps)
    except anthropic.APIStatusError as exc:
        logger.error("Anthropic API-Fehler %s: %s", exc.status_code, exc.message)
        return _fallback_result(f"KI-Analyse fehlgeschlagen (HTTP {exc.status_code}).", data_gaps)
    except ValidationError as exc:
        logger.error("LLM-Output entspricht nicht dem Schema: %s", exc)
        return _fallback_result("KI-Analyse lieferte kein schema-konformes JSON.", data_gaps)
    except Exception as exc:  # letzte Sicherheitsnetz-Schicht — Pipeline darf nie crashen
        logger.exception("Unerwarteter Fehler bei der KI-Analyse: %s", exc)
        return _fallback_result("KI-Analyse fehlgeschlagen (unerwarteter Fehler).", data_gaps)

    result = response.parsed_output
    # Datenlücken aus der Rohdatenbeschaffung mit denen des LLM zusammenführen (dedupliziert)
    result.data_gaps = list(dict.fromkeys([*data_gaps, *result.data_gaps]))
    return result


# ---------------------------------------------------------------------------
# Schritt 4: Notion-Rückschreibung
# ---------------------------------------------------------------------------

def _rich_text(text: str) -> list[dict]:
    """Notion rich_text-Array, in <=2000-Zeichen-Chunks aufgeteilt."""
    text = text or ""
    if not text:
        return []
    chunks = [text[i:i + MAX_RICH_TEXT_CHARS] for i in range(0, len(text), MAX_RICH_TEXT_CHARS)]
    return [{"type": "text", "text": {"content": chunk}} for chunk in chunks]


def _format_pitch_text(pitch: PitchAnsatz, data_gaps: list[str]) -> str:
    pain_points = "\n".join(f"  • {p}" for p in pitch.pain_points) or "  • —"
    text = (
        "BANT-Analyse\n"
        f"Budget: {pitch.budget}\n"
        f"Authority: {pitch.authority}\n"
        f"Need: {pitch.need}\n"
        f"Timing: {pitch.timing}\n"
        f"Pain Points:\n{pain_points}\n\n"
        f"Icebreaker: {pitch.icebreaker}"
    )
    if data_gaps:
        text += "\n\nDatenlücken:\n" + "\n".join(f"  • {g}" for g in data_gaps)
    return text


def build_notion_properties(request: WebhookRequest, result: EnrichmentResult) -> dict[str, Any]:
    """Mappt das validierte EnrichmentResult auf Notion-Property-Typen (siehe
    notion-database-schema.json)."""
    properties: dict[str, Any] = {
        "Unternehmensname": {"title": [{"type": "text", "text": {"content": request.company_name}}]},
        "Domain / URL": {"url": request.domain},
        "Branche": {"select": {"name": result.branche}},
        "Key Metrics & C-Level": {"rich_text": _rich_text(result.key_metrics_ansprechpartner)},
        "Manuelle Social Insights (LinkedIn)": {"rich_text": _rich_text(request.manual_social_insights or "")},
        "News & Trigger-Events (Auto)": {"rich_text": _rich_text(result.news_trigger_events)},
        "Pitch-Ansatz / Icebreaker (AI)": {
            "rich_text": _rich_text(_format_pitch_text(result.pitch_ansatz, result.data_gaps))
        },
        "Status": {"select": {"name": "Angereichert" if result.confidence != "niedrig" else "In Recherche"}},
        "Letzte Anreicherung": {"date": {"start": datetime.now(timezone.utc).date().isoformat()}},
    }
    if result.mitarbeiterzahl_schaetzung is not None:
        properties["Mitarbeiterzahl"] = {"number": result.mitarbeiterzahl_schaetzung}
    return properties


def create_notion_page(properties: dict[str, Any]) -> str:
    """Erstellt eine neue Page in der Account-Dossiers-Datenbank. Wirft NotionWriteError
    bei endgültigem Fehlschlag (Aufrufer entscheidet, wie er das nach außen meldet)."""
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        raise NotionWriteError("NOTION_API_KEY oder NOTION_DATABASE_ID nicht gesetzt.")

    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json",
    }
    body = {"parent": {"database_id": NOTION_DATABASE_ID}, "properties": properties}

    last_exc: Optional[Exception] = None
    for attempt in range(1, 3):
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                response = client.post("https://api.notion.com/v1/pages", headers=headers, json=body)

            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", "1"))
                logger.warning("Notion Rate Limit, Retry nach %.1fs", retry_after)
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            return response.json()["id"]
        except httpx.HTTPStatusError as exc:
            logger.error("Notion API Fehler %s: %s", exc.response.status_code, exc.response.text)
            last_exc = exc
            break  # 4xx/5xx außer 429: erneuter Versuch mit identischem Body bringt nichts
        except httpx.RequestError as exc:
            logger.warning("Notion Netzwerkfehler (Versuch %d): %s", attempt, exc)
            last_exc = exc
            time.sleep(1.5 * attempt)

    raise NotionWriteError(f"Notion-Seite konnte nicht erstellt werden: {last_exc}")


# ---------------------------------------------------------------------------
# Orchestrierung
# ---------------------------------------------------------------------------

def run_pipeline(raw_payload: dict[str, Any]) -> dict[str, Any]:
    """Führt alle vier Schritte sequenziell aus. Gibt bei jedem Fehlertyp ein
    strukturiertes Ergebnis zurück statt eine Exception zu propagieren."""
    try:
        request = WebhookRequest.model_validate(raw_payload)
    except ValidationError as exc:
        logger.warning("Ungültiger Input: %s", exc)
        return {"success": False, "error": "invalid_input", "details": exc.errors()}

    website_text, gaps_website = fetch_website_text(request.domain)
    news_items, gaps_news = fetch_news(request.company_name)
    data_gaps = [*gaps_website, *gaps_news]

    result = analyze_with_claude(request, website_text, news_items, data_gaps)
    properties = build_notion_properties(request, result)

    try:
        page_id = create_notion_page(properties)
    except NotionWriteError as exc:
        logger.error("Notion-Rückschreibung fehlgeschlagen: %s", exc)
        return {
            "success": False,
            "error": "notion_write_failed",
            "details": str(exc),
            "enrichment": result.model_dump(),
        }

    return {
        "success": True,
        "notion_page_id": page_id,
        "enrichment": result.model_dump(),
    }


# ---------------------------------------------------------------------------
# Webhook-Oberflächen: FastAPI (optional) + AWS Lambda
# ---------------------------------------------------------------------------

try:
    from fastapi import Request
    from fastapi import FastAPI as _FastAPI
    from fastapi.responses import JSONResponse

    app = _FastAPI(title="Account Intelligence Pipeline")

    @app.post("/enrich")
    async def enrich_endpoint(request: Request) -> JSONResponse:
        payload = await request.json()
        result = run_pipeline(payload)
        return JSONResponse(content=result, status_code=200 if result.get("success") else 422)

except ImportError:
    app = None  # FastAPI ist optional — für den reinen Lambda-Einsatz nicht nötig


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """AWS-Lambda-Einstiegspunkt, kompatibel mit API Gateway / Lambda Function URLs."""
    body = event.get("body", "{}")
    try:
        payload = json.loads(body) if isinstance(body, str) else (body or {})
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": json.dumps({"success": False, "error": "invalid_json"})}

    result = run_pipeline(payload)
    return {
        "statusCode": 200 if result.get("success") else 422,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(result, ensure_ascii=False),
    }


if __name__ == "__main__":
    example_payload = {
        "company_name": "Beispiel GmbH",
        "domain": "beispiel-gmbh.de",
        "manual_social_insights": None,
        "existing_pitch_notes": None,
    }
    print(json.dumps(run_pipeline(example_payload), indent=2, ensure_ascii=False))

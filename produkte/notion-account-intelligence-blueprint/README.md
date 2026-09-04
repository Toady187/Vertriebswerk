# Account Intelligence Blueprint (Notion)

Notion-Datenbank + Automatisierungs-Blueprint für KAM/B2B-Vertriebler, die Account Dossiers ohne unzuverlässiges LinkedIn-Scraping pflegen wollen. Paradigma: offline-stabil, datensparsam, nur offizielle Quellen (Website-Text via Reader-API, Google News RSS) + manueller Freitext für Social Signals.

## Dateien

| Datei | Zweck |
|---|---|
| `notion-database-schema.json` | Notion API Property-Schema für die Datenbank "Account Dossiers" |
| `webhook-payload-schema.json` | JSON Schema (Request an LLM + Response vom LLM) für den Make/n8n-Webhook |
| `system-prompt.md` | Fertiger System-Prompt für den LLM-Knoten inkl. Integrationshinweisen |
| `pipeline.py` | Phase 2: Python-Kern-Modul, das den kompletten Datenfluss selbst ausführt (Website + News → Claude → Notion) |
| `requirements.txt` | Python-Abhängigkeiten für `pipeline.py` |
| `.env.example` | Vorlage für die benötigten Umgebungsvariablen |
| `shop-produktseite.md` | Phase 3: Produktseiten-Text für vertriebswerk.shop (Problem/Lösung/Value Prop/Preis) |
| `setup-guide.md` | Phase 3: Quelltext des Kunden-Setup-Guides ("In 10 Minuten zum ersten KI-Dossier") |
| `generate_setup_guide_pdf.py` | Baut `setup-guide.pdf` aus `setup-guide.md`-Inhalten im Vertriebswerk-CI (Navy/Teal, DM Sans/DM Serif Display) |
| `setup-guide.pdf` | Fertiges Kunden-PDF, wird beim Kauf mitgeliefert |
| `assets/` | Fonts + Logo für den PDF-Build (aus vertriebswerk.shop/index.html übernommen) |
| `blueprint-n8n.json` | Phase 4: Importierbarer n8n-Workflow (Ein-Klick-Import) — bildet den kompletten Flow ab: Webhook → Jina Reader → Google News RSS → Claude (mit eingebettetem System-Prompt) → Notion |
| `produktkarte-index.html` | Phase 4: Fertiger `.tcard`-Snippet für `index.html`, noch mit Platzhalter-Checkout-URL |
| `test_e2e.py` | Phase 4: Manueller Live-Smoke-Test gegen echte Anthropic-/Jina-/Notion-APIs vor Go-Live |
| `ZIP-MANIFEST.md` | Phase 4: Checkliste, welche Dateien ins Lemon-Squeezy-Auslieferungs-ZIP gehören (und welche nicht) |

## Notion-Datenbank "Account Dossiers"

| Feld | Typ | Befüllung |
|---|---|---|
| Unternehmensname | Title | manuell |
| Domain / URL | URL | manuell |
| Branche | Select | AI (klassifiziert) |
| Mitarbeiterzahl | Number | AI (nur wenn belegt, sonst leer) |
| Key Metrics & C-Level | Rich Text | AI |
| Manuelle Social Insights (LinkedIn) | Rich Text | **User Input** — nie automatisch überschrieben |
| News & Trigger-Events (Auto) | Rich Text | AI, aus Google News RSS |
| Pitch-Ansatz / Icebreaker (AI) | Rich Text | AI, BANT-strukturiert |
| Status, Letzte Anreicherung, Owner | Select / Date / Person | Prozess-Metadaten (empfohlene Ergänzung, siehe JSON) |

## Datenfluss (Make.com / n8n)

```
1. Trigger
   ├─ Notion-Button "Anreichern" auf einer Account-Page  ODER
   └─ Wöchentlicher Scheduler über alle Accounts mit Status ≠ "Verloren"

2. Rohdaten sammeln
   ├─ Notion API: Page lesen (Domain, manuelle Social Insights, existing Pitch)
   ├─ Jina AI Reader: GET https://r.jina.ai/<domain>  → bereinigter Website-Text
   └─ Google News RSS: GET https://news.google.com/rss/search?q=<Firmenname>&hl=de&gl=DE
      → XML parsen → Top 10–15 Items (title, source, pubDate, link, description)

3. Payload bauen (AccountEnrichmentRequest, siehe webhook-payload-schema.json)

4. LLM-Knoten (Claude/GPT, JSON-Mode)
   → System-Prompt aus system-prompt.md
   → Output: AccountEnrichmentResponse (JSON)

5. Validierung
   → Gegen JSON-Schema prüfen; bei Fehler 1x Retry mit Fehlermeldung im Kontext
   → Bei zweitem Fehler: Fehler-Log-Sheet statt Workflow-Abbruch (offline-stabil)

6. Rückschreiben
   → pitch_ansatz-Objekt zu formatiertem Rich-Text zusammensetzen
   → Notion API PATCH auf die Ziel-Page (Branche, Mitarbeiterzahl,
     Key Metrics, News-Feld, Pitch-Feld, Status → "Angereichert",
     Letzte Anreicherung → heute)
   → "Manuelle Social Insights" NIE überschreiben — nur lesend einbeziehen
```

## Phase 2: Python-Pipeline (`pipeline.py`)

Ersetzt die Schritte 2–6 des obigen Make/n8n-Flows durch ein eigenständiges Python-Modul, das
als FastAPI-Endpoint oder AWS-Lambda-Handler läuft. Der Trigger (Notion-Button, Scheduler) bleibt
weiterhin Sache von Make/n8n oder Notion Automations — die schickt nur noch
`{company_name, domain, manual_social_insights?, existing_pitch_notes?}` an die Pipeline.

**Ablauf:** Input-Validierung (Pydantic) → `fetch_website_text()` (Jina AI Reader) und
`fetch_news()` (Google News RSS) parallel-fehlerresistent → `analyze_with_claude()` (Anthropic
Messages API, `client.messages.parse()` mit `EnrichmentResult`-Pydantic-Modell als
`output_format`, damit der Output garantiert schema-konform zurückkommt) → `create_notion_page()`
(POST auf `/v1/pages`, legt einen neuen Eintrag in der Datenbank an).

**Fehlerresistenz:** Jeder Netzwerk-/API-Aufruf ist einzeln abgesichert — schlägt Jina AI Reader
oder der RSS-Feed fehl, läuft die Pipeline mit leeren Rohdaten weiter und trägt die Ursache in
`data_gaps` ein; schlägt der Anthropic-Call fehl (Rate-Limit, Auth, Netzwerk, ungültiges JSON),
liefert `analyze_with_claude()` ein `EnrichmentResult` mit `confidence: "niedrig"` statt zu
crashen. Nur ein endgültig fehlgeschlagener Notion-Schreibvorgang führt zu `success: false` in
der Antwort — alle anderen Fehlerklassen werden intern aufgefangen.

**Betrieb:**

```bash
pip install -r requirements.txt
cp .env.example .env   # ANTHROPIC_API_KEY, NOTION_API_KEY, NOTION_DATABASE_ID setzen

# Lokal als FastAPI-Server:
uvicorn pipeline:app --reload
# POST http://localhost:8000/enrich  {"company_name": "...", "domain": "..."}

# Als AWS Lambda: Handler pipeline.lambda_handler, Event-Body = obiges JSON.
```

**Hinweis zur Modellwahl:** Die Aufgabenstellung nannte `claude-3-5-sonnet-20241022` — ein
mittlerweile veraltetes/vsl. abgekündigtes Modell. `pipeline.py` verwendet standardmäßig die
aktuelle Sonnet-Generation (`claude-sonnet-5`), überschreibbar via `ANTHROPIC_MODEL`.

## Phase 4: Go-Live-Vorbereitung

**n8n-Import statt Handaufbau:** `blueprint-n8n.json` bildet den kompletten Flow (10 Nodes:
Webhook → Jina Reader → Google News RSS → LLM-Payload bauen → Claude → Antwort parsen →
Notion-Properties bauen → Notion-Seite erstellen → Antwort senden) fertig verdrahtet ab,
inklusive des vollständigen System-Prompts. Import über **n8n → Workflows → Import from
File**; danach nur noch `ANTHROPIC_API_KEY`, `NOTION_API_KEY`, `NOTION_DATABASE_ID` als
Umgebungsvariablen der n8n-Instanz setzen. Make.com bleibt beim manuellen Aufbau (siehe
oben) — Make-Blueprints sind kontogebunden und nicht portabel exportierbar.

**Vor dem Verkaufsstart real testen:** `test_e2e.py` führt `run_pipeline()` gegen echte
Anthropic-/Jina-/Notion-APIs aus (kein Mocking) und prüft das Ergebnis gegen eine Reihe von
Smoke-Test-Kriterien (Branche klassifiziert, Icebreaker nicht leer, Notion-Page-ID
zurückgegeben, …). Läuft standardmäßig als Trockenlauf (prüft nur Env-Vars); echter Aufruf
nur mit explizitem `--confirm`:

```bash
python3 test_e2e.py --company "Deine Test GmbH" --domain example.com --confirm
```

Auf eine **Test-Notion-Datenbank** zeigen lassen (`NOTION_DATABASE_ID`), nicht auf
Produktivdaten — das Skript legt bei Erfolg eine echte Seite an.

**Shop-Integration:** `produktkarte-index.html` enthält den fertigen `.tcard`-Snippet für
`index.html` (Platzhalter `[[LEMON_SQUEEZY_CHECKOUT_URL]]` nach Anlage des Lemon-Squeezy-
Produkts ersetzen). `ZIP-MANIFEST.md` listet exakt, welche Dateien in das
Kunden-Auslieferungs-ZIP gehören — bewusst eine kleinere Teilmenge als dieser Ordner, da
z. B. `README.md`, `shop-produktseite.md` und das PDF-Build-Tooling interne Dokumente sind.

## Design-Entscheidungen

- **Kein LinkedIn-Scraping:** LinkedIn-Posts werden vom Nutzer selbst als Freitext eingefügt (Feld "Manuelle Social Insights"). Der Workflow liest dieses Feld nur als Kontext für das LLM, schreibt es nie automatisch.
- **Datensparsamkeit:** Der LLM-Prompt verbietet explizit das Erfinden von Fakten/Kontakten; fehlende Informationen landen in `data_gaps` statt geraten zu werden.
- **Offline-Stabilität:** Fällt Jina AI Reader oder der RSS-Feed aus, läuft der Workflow mit den verbleibenden Quellen weiter (leeres `raw_website_text` bzw. leeres `raw_news_items`-Array ist laut Schema erlaubt); das LLM setzt `confidence: "niedrig"` und dokumentiert die Lücke, statt den Lauf abzubrechen.
- **BANT + Pain-Points:** Das Pitch-Feld ist bewusst strukturiert (nicht Fließtext ohne Gliederung), damit der KAM vor einem Call in Sekunden Budget/Authority/Need/Timing überfliegen kann.

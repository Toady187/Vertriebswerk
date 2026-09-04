<!-- Quelle für setup-guide.pdf (siehe generate_setup_guide_pdf.py). Änderungen hier
     vornehmen und PDF neu generieren, nicht umgekehrt. -->

# Account Intelligence Blueprint
## In 10 Minuten zu deinem ersten KI-Dossier

Diese Anleitung führt dich einmal komplett durch das Setup: Notion-Template, Automatisierung, API-Keys. Kein Coding-Wissen nötig — nur die Bereitschaft, dreimal Copy-Paste zu machen.

---

## Bevor du startest

Halte bereit:

- [ ] Einen Notion-Account (kostenloser Plan reicht)
- [ ] Einen Anthropic API-Key (console.anthropic.com)
- [ ] Fünf Minuten für die Notion-Integration
- [ ] Entweder einen Make.com-/n8n-Account **oder** Python 3.10+ lokal

---

## Schritt 1 — Notion-Template duplizieren

1. Öffne den Notion-Duplizieren-Link: **[[NOTION_DUPLICATE_LINK]]** — du findest ihn auch in deiner Bestell-E-Mail.
2. Klicke oben rechts auf **Duplicate** und wähle deinen Ziel-Workspace.
3. Die Datenbank **„Account Dossiers"** liegt danach in deinem Workspace — verschiebe sie an die gewünschte Stelle (z. B. unter dein Sales-Hub).
4. Öffne **Settings → Connections** in Notion und lege eine neue Integration an (oder nutze eine bestehende): *My Integrations → New Integration → nur „Read/Update/Insert content"-Rechte nötig.*
5. Verbinde die Integration explizit mit der Datenbank „Account Dossiers": Datenbank öffnen → **„...“-Menü → Connections → deine Integration hinzufügen.**

   *Dieser Schritt wird am häufigsten übersprungen — ohne ihn kann die Automatisierung nicht schreiben, obwohl der API-Key korrekt ist.*

6. Kopiere die **Database-ID** aus der Browser-URL der Datenbank (der 32-stellige Code direkt vor `?v=`). Notiere sie — du brauchst sie in Schritt 3.

---

## Schritt 2 — Automatisierung anbinden

Wähle einen der beiden Wege. Beide führen zum selben Ergebnis.

### Weg A: Python-Skript (`pipeline.py`) — für Selbst-Hoster

1. Entpacke den Ordner aus deinem Download.
2. Installiere die Abhängigkeiten: `pip install -r requirements.txt`
3. Kopiere `.env.example` zu `.env`.
4. Starte lokal zum Testen: `uvicorn pipeline:app --reload`
5. Für den produktiven Einsatz: als AWS-Lambda-Funktion deployen (Handler: `pipeline.lambda_handler`) oder auf einem eigenen Server hinter einem Reverse Proxy betreiben.

### Weg B: n8n oder Make.com — ohne eigenes Hosting

**n8n (empfohlen — Ein-Klick-Import):**

1. n8n öffnen → **Workflows → Import from File** (oder Strg/Cmd+O) → `blueprint-n8n.json` aus deinem Download auswählen.
2. n8n zeigt den kompletten Workflow fertig verdrahtet — Webhook, Website-Abruf, News-RSS, Claude-Analyse (System-Prompt ist bereits enthalten) und Notion-Rückschreibung.
3. Trage `ANTHROPIC_API_KEY`, `NOTION_API_KEY` und `NOTION_DATABASE_ID` als Umgebungsvariablen deiner n8n-Instanz ein (**Settings → Environment Variables**) — oder ersetze die `$env...`-Ausdrücke direkt in den beiden HTTP-Request-Knoten durch n8n-Credentials.
4. Workflow aktivieren, Webhook-URL kopieren, an deinen Trigger (Notion-Button, Scheduler o. Ä.) hängen.

**Make.com:**

Ein Ein-Klick-Import ist bei Make.com anders als bei n8n nicht möglich — Make-Blueprints sind an das jeweilige Konto gebunden und lassen sich nicht kontenübergreifend exportieren. Baue die 5 Module stattdessen manuell nach:

1. Neues Szenario mit **Webhook-Trigger**.
2. **HTTP-Request-Modul** für den Website-Abruf: `GET https://r.jina.ai/{domain}`
3. Zweites **HTTP-Request-Modul** für die News: `GET https://news.google.com/rss/search?q={firmenname}&hl=de&gl=DE&ceid=DE:de`
4. **LLM-Modul** (Claude) mit dem System-Prompt aus `system-prompt.md` unverändert eingefügt.
5. **Notion-Modul „Create a Database Item"**, verbunden mit deinem Notion-Account aus Schritt 1.

*Ausführliche Modul-für-Modul-Beschreibung inkl. Feldmapping: siehe `README.md` im Blueprint-Ordner.*

---

## Schritt 3 — API-Keys hinterlegen

| Key | Woher | Wohin |
|---|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys → Create Key | `.env` (Python) · n8n Environment Variables · Connection im LLM-Modul (Make) |
| `NOTION_API_KEY` | Notion → My Integrations → dein Integration Token | `.env` (Python) · n8n Environment Variables · Notion-Connection (Make) |
| `NOTION_DATABASE_ID` | aus Schritt 1.6 | `.env` (Python) · n8n Environment Variables · direkt im Notion-Modul auswählen (Make) |

**Sicherheitshinweis:** Trage Keys ausschließlich in `.env`-Dateien oder die Connection-Verwaltung von Make.com/n8n ein — niemals in ein Notion-Textfeld, einen Screenshot oder eine Chat-Nachricht.

### Erster Testlauf

Trage eine dir bekannte Firma ein (Name + Domain) und starte den Workflow einmal manuell. Prüfe:

- Ist die Branche plausibel klassifiziert?
- Wirkt der Pitch-Ansatz wie ein guter erster Entwurf — nicht wie Fantasie?
- Sind Datenlücken dort ausgewiesen, wo tatsächlich wenig öffentliche Information existiert?

Wenn ja: Setup abgeschlossen. Wenn nein: Prüfe zuerst Schritt 1.5 (Connection) — das ist die häufigste Fehlerquelle.

---

## Best Practices für den täglichen Einsatz

**Wöchentlicher Rhythmus statt Dauerlauf.** Reichere Accounts einmal pro Woche automatisch neu an, nicht bei jedem Klick — das spart API-Kosten und hält die Daten trotzdem aktuell genug für den Vertriebsalltag.

**Manuelle Social Insights sind Chefsache.** Trage LinkedIn-Beobachtungen selbst ein, kurz nachdem du sie gelesen hast — nicht drei Wochen später aus dem Gedächtnis.

**Ein Datenlücken-Eintrag ist ein Signal, kein Fehler.** Er zeigt dir genau, wo du selbst nachfassen solltest, statt dir eine erfundene Zahl unterzujubeln.

**Der Icebreaker ist ein Entwurf, kein Skript.** Bring ihn in deine eigenen Worte, bevor du ihn im Gespräch verwendest.

**Vor dem Call reicht ein Zwei-Minuten-Review.** Du musst das Dossier nicht bei jedem Gespräch neu durcharbeiten — ein kurzer Blick auf News-Trigger und Pitch-Ansatz genügt.

---

Fragen zum Setup? kontakt@vertriebswerk.shop

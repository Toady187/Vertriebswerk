# Account Intelligence Blueprint (Notion)

Notion-Datenbank + Automatisierungs-Blueprint für KAM/B2B-Vertriebler, die Account Dossiers ohne unzuverlässiges LinkedIn-Scraping pflegen wollen. Paradigma: offline-stabil, datensparsam, nur offizielle Quellen (Website-Text via Reader-API, Google News RSS) + manueller Freitext für Social Signals.

## Dateien

| Datei | Zweck |
|---|---|
| `notion-database-schema.json` | Notion API Property-Schema für die Datenbank "Account Dossiers" |
| `webhook-payload-schema.json` | JSON Schema (Request an LLM + Response vom LLM) für den Make/n8n-Webhook |
| `system-prompt.md` | Fertiger System-Prompt für den LLM-Knoten inkl. Integrationshinweisen |

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

## Design-Entscheidungen

- **Kein LinkedIn-Scraping:** LinkedIn-Posts werden vom Nutzer selbst als Freitext eingefügt (Feld "Manuelle Social Insights"). Der Workflow liest dieses Feld nur als Kontext für das LLM, schreibt es nie automatisch.
- **Datensparsamkeit:** Der LLM-Prompt verbietet explizit das Erfinden von Fakten/Kontakten; fehlende Informationen landen in `data_gaps` statt geraten zu werden.
- **Offline-Stabilität:** Fällt Jina AI Reader oder der RSS-Feed aus, läuft der Workflow mit den verbleibenden Quellen weiter (leeres `raw_website_text` bzw. leeres `raw_news_items`-Array ist laut Schema erlaubt); das LLM setzt `confidence: "niedrig"` und dokumentiert die Lücke, statt den Lauf abzubrechen.
- **BANT + Pain-Points:** Das Pitch-Feld ist bewusst strukturiert (nicht Fließtext ohne Gliederung), damit der KAM vor einem Call in Sekunden Budget/Authority/Need/Timing überfliegen kann.

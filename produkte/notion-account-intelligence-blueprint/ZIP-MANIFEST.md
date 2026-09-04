# ZIP-Paket für Lemon Squeezy — Auslieferungs-Checkliste

Ziel-Datei: **`Account-Intelligence-Blueprint.zip`**

⚠️ **Vor dem Packen zwingend erledigen:** `[[NOTION_DUPLICATE_LINK]]` in `setup-guide.md`
UND `generate_setup_guide_pdf.py` durch den echten Notion-Duplizieren-Link ersetzen, dann
`python3 generate_setup_guide_pdf.py` neu laufen lassen. Ein ZIP mit Platzhalter-Link
darf nicht ausgeliefert werden.

## Im ZIP enthalten (Kunden-Deliverables)

- [ ] `pipeline.py` — Python-Automatisierung (FastAPI/Lambda)
- [ ] `requirements.txt` — Python-Abhängigkeiten
- [ ] `.env.example` — Vorlage für Umgebungsvariablen
- [ ] `blueprint-n8n.json` — importierbarer n8n-Workflow (Ein-Klick-Import)
- [ ] `system-prompt.md` — System-Prompt für den LLM-Knoten (für Make.com-Handaufbau)
- [ ] `webhook-payload-schema.json` — Request-/Response-Schema (für Make.com-Handaufbau)
- [ ] `notion-database-schema.json` — Notion-Property-Referenz (welche Felder wie heißen müssen)
- [ ] `Setup-Guide.pdf` — **umbenannt** aus `setup-guide.pdf` (kundenfreundlicher Dateiname), mit echtem Duplizieren-Link

## Explizit NICHT im ZIP (internes Material)

| Datei | Warum ausgeschlossen |
|---|---|
| `README.md` | Internes Engineering-Dokument (Phasen-Sprache, Architektur-Notizen) — nicht für Kunden formuliert |
| `shop-produktseite.md` | Marketing-Copy für den eigenen Shop, nicht Teil des Produkts |
| `produktkarte-index.html` | Interner Website-Snippet |
| `generate_setup_guide_pdf.py` + `assets/` | Build-Tooling für das PDF (Fonts, Logo, Skript) — Kunde braucht nur das fertige PDF |
| `test_e2e.py` | Interner Pre-Launch-Smoke-Test, keine Kundenfunktion |
| `setup-guide.md` | Quelltext des PDFs — Kunde bekommt nur das fertige `Setup-Guide.pdf` |
| `ZIP-MANIFEST.md` (diese Datei) | Interne Packliste |
| `.git/`, `__pycache__/`, `.env` (falls lokal angelegt) | Kein Produktbestandteil / potenziell sensibel |

## Packen (Referenzbefehl, lokal ausführen)

```bash
cd produkte/notion-account-intelligence-blueprint
mkdir -p /tmp/aib-release
cp pipeline.py requirements.txt .env.example blueprint-n8n.json \
   system-prompt.md webhook-payload-schema.json notion-database-schema.json \
   /tmp/aib-release/
cp setup-guide.pdf /tmp/aib-release/Setup-Guide.pdf
cd /tmp/aib-release && zip -r Account-Intelligence-Blueprint.zip . -x ".*"
```

## Vor dem Upload zu Lemon Squeezy prüfen

- [ ] ZIP entpackt sich sauber, alle 8 Dateien vorhanden, keine Platzhalter-Reste (`grep -r "\[\[" .` sollte leer sein)
- [ ] `Setup-Guide.pdf` öffnet sich und zeigt den echten Notion-Link, nicht `[[NOTION_DUPLICATE_LINK]]`
- [ ] `.env.example` enthält keine echten Keys (nur leere Platzhalter-Zeilen)
- [ ] Lemon-Squeezy-Produktbeschreibung nutzt den Text aus `shop-produktseite.md` (wird separat gepflegt, nicht mit ausgeliefert)

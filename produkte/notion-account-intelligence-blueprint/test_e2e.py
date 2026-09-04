"""Manueller Live-Smoke-Test gegen echte APIs — vor Go-Live einmal ausführen.

Ruft run_pipeline() aus pipeline.py mit ECHTEN Anthropic-/Jina-/Notion-Aufrufen auf
(kein Mocking). Kostet reale API-Nutzung und legt bei Erfolg eine echte Seite in
deiner Notion-Test-Datenbank an — deshalb kein automatischer CI-Test, sondern ein
bewusst manuell gestartetes Skript mit explizitem Bestätigungs-Flag.

Voraussetzungen:
- .env mit ANTHROPIC_API_KEY, NOTION_API_KEY, NOTION_DATABASE_ID (siehe .env.example)
  — NOTION_DATABASE_ID sollte auf eine TEST-Datenbank zeigen, nicht auf Produktivdaten.
- Die Test-Datenbank muss die Struktur aus notion-database-schema.json haben und mit
  der Integration verbunden sein (siehe Setup-Guide Schritt 1.5).

Aufruf:
    python3 test_e2e.py --company "Deine Test GmbH" --domain example.com --confirm

Ohne --confirm bricht das Skript vor jedem echten API-Call ab (Trockenlauf: prüft
nur, ob die Umgebungsvariablen gesetzt sind).
"""

import argparse
import json
import os
import sys

REQUIRED_ENV_VARS = ["ANTHROPIC_API_KEY", "NOTION_API_KEY", "NOTION_DATABASE_ID"]


def load_dotenv_if_present() -> None:
    """Minimaler .env-Loader ohne Zusatzabhängigkeit (kein python-dotenv im Projekt).
    Setzt nur Variablen, die noch nicht in der Shell-Umgebung gesetzt sind."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


load_dotenv_if_present()

import pipeline  # noqa: E402  (nach load_dotenv_if_present, damit os.getenv() die .env sieht)


def check_env() -> list[str]:
    missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
    return missing


def run_smoke_test(company_name: str, domain: str) -> int:
    """Führt run_pipeline() live aus und prüft das Ergebnis gegen eine Reihe von
    Smoke-Test-Kriterien. Gibt 0 bei vollem Erfolg zurück, sonst 1."""
    print(f"→ Starte Live-Test für '{company_name}' ({domain}) ...\n")

    result = pipeline.run_pipeline({
        "company_name": company_name,
        "domain": domain,
        "manual_social_insights": None,
        "existing_pitch_notes": None,
    })

    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()

    checks: list[tuple[str, bool]] = []

    checks.append(("Pipeline lief ohne unbehandelte Exception durch", True))
    checks.append(("Ergebnis enthält 'success'-Feld", "success" in result))

    enrichment = result.get("enrichment")
    checks.append(("Ergebnis enthält 'enrichment'-Objekt", enrichment is not None))

    if enrichment:
        checks.append(("Branche wurde klassifiziert", bool(enrichment.get("branche"))))
        checks.append(("Confidence-Feld vorhanden", enrichment.get("confidence") in ("hoch", "mittel", "niedrig")))
        checks.append(("Pitch-Ansatz-Objekt vorhanden", isinstance(enrichment.get("pitch_ansatz"), dict)))
        pitch = enrichment.get("pitch_ansatz") or {}
        checks.append(("Icebreaker ist nicht leer", bool((pitch.get("icebreaker") or "").strip())))
        checks.append(("data_gaps ist eine Liste (auch wenn leer)", isinstance(enrichment.get("data_gaps"), list)))

    if result.get("success"):
        checks.append(("Notion-Page-ID wurde zurückgegeben", bool(result.get("notion_page_id"))))
    else:
        checks.append((f"Fehlerursache dokumentiert ({result.get('error')})", "error" in result))

    print("Smoke-Test-Ergebnis:")
    all_ok = True
    for label, ok in checks:
        print(f"  [{'OK' if ok else 'FEHLT'}] {label}")
        all_ok = all_ok and ok

    print()
    if result.get("success"):
        print(
            f"✓ Notion-Seite erstellt (ID: {result['notion_page_id']}). "
            "Jetzt manuell in Notion öffnen und Feldinhalte gegenlesen:"
        )
        print("  - Branche plausibel? Pitch-Ansatz wie ein guter Entwurf, nicht wie Fantasie?")
        print("  - Rich-Text-Felder korrekt formatiert (keine abgeschnittenen Chunks)?")
        print("  - Datenlücken dort ausgewiesen, wo tatsächlich wenig öffentliche Info existiert?")
    else:
        print(f"✗ Pipeline meldet Fehler: {result.get('error')} — {result.get('details')}")

    return 0 if (all_ok and result.get("success")) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--company", default="Vertriebswerk Test GmbH", help="Firmenname für den Testlauf")
    parser.add_argument("--domain", default="vertriebswerk.shop", help="Domain für den Testlauf")
    parser.add_argument(
        "--confirm", action="store_true",
        help="Bestätigt den echten API-Aufruf (Anthropic + Notion + Jina). Ohne dieses "
             "Flag wird nur die Umgebungskonfiguration geprüft (Trockenlauf).",
    )
    args = parser.parse_args()

    missing = check_env()
    if missing:
        print(f"✗ Fehlende Umgebungsvariablen: {', '.join(missing)}")
        print("  Siehe .env.example — Werte in eine .env-Datei im selben Ordner eintragen.")
        return 1
    print("✓ Alle benötigten Umgebungsvariablen sind gesetzt.\n")

    if not args.confirm:
        print(
            "Trockenlauf beendet (kein --confirm übergeben). Kein echter API-Call wurde "
            "ausgeführt. Zum echten Smoke-Test:\n"
            f"  python3 test_e2e.py --company \"{args.company}\" --domain {args.domain} --confirm"
        )
        return 0

    print(
        "⚠ Achtung: Dieser Lauf ruft echte Anthropic-/Jina-/Notion-APIs auf und legt bei "
        f"Erfolg eine echte Seite in der Datenbank {os.getenv('NOTION_DATABASE_ID')} an.\n"
    )
    return run_smoke_test(args.company, args.domain)


if __name__ == "__main__":
    sys.exit(main())

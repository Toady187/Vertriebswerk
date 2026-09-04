"""Baut setup-guide.pdf im Vertriebswerk-CI (Navy/Teal, DM Sans + DM Serif Display).

Inhalt ist bewusst direkt in Flowables geschrieben (kein Markdown-Parser) — Quelle
der Formulierungen ist setup-guide.md; bei inhaltlichen Änderungen dort UND hier
pflegen. Ausführen mit: python3 generate_setup_guide_pdf.py
"""

import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, NextPageTemplate, PageBreak,
    Paragraph, Spacer, Table, TableStyle, Image, KeepTogether,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE_DIR, "assets")
OUTPUT_PATH = os.path.join(BASE_DIR, "setup-guide.pdf")

# ---------------------------------------------------------------------------
# Brand: Farben & Fonts (aus dem CSS von vertriebswerk.shop/index.html übernommen)
# ---------------------------------------------------------------------------

NAVY = colors.HexColor("#1B2A4A")
NAVY_LIGHT = colors.HexColor("#2D4575")
TEAL = colors.HexColor("#00A884")
OFF_WHITE = colors.HexColor("#F7F4EF")
TEXT = colors.HexColor("#1C2333")
MUTED = colors.HexColor("#5B6472")
WHITE = colors.white
TINT = colors.Color(27 / 255, 42 / 255, 74 / 255, alpha=0.06)

pdfmetrics.registerFont(TTFont("DMSans", os.path.join(ASSETS, "fonts", "DMSans-Regular.ttf")))
pdfmetrics.registerFont(TTFont("DMSans-Bold", os.path.join(ASSETS, "fonts", "DMSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DMSerif", os.path.join(ASSETS, "fonts", "DMSerifDisplay-Regular.ttf")))

PAGE_W, PAGE_H = A4
MARGIN = 2.2 * cm

# ---------------------------------------------------------------------------
# Absatzstile
# ---------------------------------------------------------------------------

styles = {
    "cover_title": ParagraphStyle(
        "cover_title", fontName="DMSerif", fontSize=30, leading=36, textColor=WHITE,
    ),
    "cover_sub": ParagraphStyle(
        "cover_sub", fontName="DMSans", fontSize=13, leading=19, textColor=colors.HexColor("#C9D2E3"),
        spaceBefore=10,
    ),
    "cover_tag": ParagraphStyle(
        "cover_tag", fontName="DMSans-Bold", fontSize=9.5, leading=12, textColor=TEAL,
        spaceAfter=14,
    ),
    "h1": ParagraphStyle(
        "h1", fontName="DMSerif", fontSize=18, leading=23, textColor=NAVY, spaceBefore=4, spaceAfter=10,
    ),
    "eyebrow": ParagraphStyle(
        "eyebrow", fontName="DMSans-Bold", fontSize=9, leading=11, textColor=TEAL,
        spaceBefore=16, spaceAfter=2,
    ),
    "h2": ParagraphStyle(
        "h2", fontName="DMSerif", fontSize=15, leading=19, textColor=NAVY, spaceAfter=8,
    ),
    "h3": ParagraphStyle(
        "h3", fontName="DMSans-Bold", fontSize=10.5, leading=14, textColor=NAVY, spaceBefore=10, spaceAfter=4,
    ),
    "body": ParagraphStyle(
        "body", fontName="DMSans", fontSize=10, leading=15.5, textColor=TEXT, spaceAfter=8,
    ),
    "body_muted": ParagraphStyle(
        "body_muted", fontName="DMSans", fontSize=9, leading=13.5, textColor=MUTED, spaceAfter=6,
    ),
    "checklist": ParagraphStyle(
        "checklist", fontName="DMSans", fontSize=10, leading=15, textColor=TEXT,
        leftIndent=2, spaceAfter=4,
    ),
    "numbered": ParagraphStyle(
        "numbered", fontName="DMSans", fontSize=10, leading=15.5, textColor=TEXT,
        leftIndent=14, spaceAfter=6,
    ),
    "note": ParagraphStyle(
        "note", fontName="DMSans", fontSize=9.5, leading=14.5, textColor=NAVY,
    ),
    "table_head": ParagraphStyle(
        "table_head", fontName="DMSans-Bold", fontSize=9.5, leading=13, textColor=WHITE,
    ),
    "table_cell": ParagraphStyle(
        "table_cell", fontName="DMSans", fontSize=9.5, leading=13.5, textColor=TEXT,
    ),
    "table_cell_mono": ParagraphStyle(
        "table_cell_mono", fontName="DMSans-Bold", fontSize=9.5, leading=13.5, textColor=NAVY,
    ),
    "footer": ParagraphStyle(
        "footer", fontName="DMSans", fontSize=8, leading=10, textColor=MUTED,
    ),
}


def eyebrow_heading(eyebrow_text: str, heading_text: str) -> KeepTogether:
    return KeepTogether([
        Paragraph(eyebrow_text.upper(), styles["eyebrow"]),
        Paragraph(heading_text, styles["h2"]),
    ])


def checklist(items: list[str]) -> list[Paragraph]:
    return [Paragraph(f"[&nbsp;&nbsp;] {item}", styles["checklist"]) for item in items]


def numbered_list(items: list[str]) -> list[Paragraph]:
    return [Paragraph(f"{i}. {item}", styles["numbered"]) for i, item in enumerate(items, start=1)]


def note_box(text: str) -> Table:
    t = Table(
        [[Paragraph(text, styles["note"])]],
        colWidths=[PAGE_W - 2 * MARGIN - 0.35 * cm],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TINT),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, TEAL),
    ]))
    return t


# ---------------------------------------------------------------------------
# Seitenrahmen (Cover vs. Inhaltsseiten)
# ---------------------------------------------------------------------------

def draw_cover_background(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    logo_path = os.path.join(ASSETS, "logo-vertriebswerk.png")
    logo_w = 4.6 * cm
    logo_h = logo_w * (65 / 263)
    canvas.drawImage(
        logo_path, MARGIN, PAGE_H - MARGIN - logo_h + 0.3 * cm,
        width=logo_w, height=logo_h, mask="auto",
    )

    canvas.setFillColor(colors.HexColor("#8B96AC"))
    canvas.setFont("DMSans", 8.5)
    canvas.drawString(MARGIN, 1.7 * cm, "vertriebswerk.shop")
    canvas.drawRightString(PAGE_W - MARGIN, 1.7 * cm, "Account Intelligence Blueprint")
    canvas.restoreState()


def draw_content_background(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(OFF_WHITE)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    canvas.setFillColor(NAVY)
    canvas.rect(0, PAGE_H - 0.35 * cm, PAGE_W, 0.35 * cm, fill=1, stroke=0)

    canvas.setStrokeColor(colors.HexColor("#D8D2C4"))
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN, 1.55 * cm, PAGE_W - MARGIN, 1.55 * cm)

    canvas.setFont("DMSans", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 1.1 * cm, "Account Intelligence Blueprint · Setup-Guide")
    canvas.drawRightString(PAGE_W - MARGIN, 1.1 * cm, f"Seite {doc.page - 1}")
    canvas.restoreState()


doc = BaseDocTemplate(
    OUTPUT_PATH, pagesize=A4,
    leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=2.1 * cm,
    title="Account Intelligence Blueprint – Setup-Guide", author="Vertriebswerk",
)

cover_frame = Frame(MARGIN, 3 * cm, PAGE_W - 2 * MARGIN, PAGE_H - 3 * cm - 6 * cm, id="cover")
content_frame = Frame(MARGIN, 2.1 * cm, PAGE_W - 2 * MARGIN, PAGE_H - 2.1 * cm - MARGIN, id="content")

doc.addPageTemplates([
    PageTemplate(id="Cover", frames=[cover_frame], onPage=draw_cover_background),
    PageTemplate(id="Content", frames=[content_frame], onPage=draw_content_background),
])

# ---------------------------------------------------------------------------
# Inhalt
# ---------------------------------------------------------------------------

story = []

# --- Cover ---
story.append(Spacer(1, 5.5 * cm))
story.append(Paragraph("SETUP-GUIDE", styles["cover_tag"]))
story.append(Paragraph("In 10 Minuten zu deinem<br/>ersten KI-Dossier", styles["cover_title"]))
story.append(Paragraph(
    "Account Intelligence Blueprint — Notion-Template, Automatisierung und "
    "API-Keys einrichten. Ohne Coding-Wissen, mit klarem Kopf.",
    styles["cover_sub"],
))

story.append(NextPageTemplate("Content"))
story.append(PageBreak())

# --- Intro ---
story.append(Paragraph("In 10 Minuten zu deinem ersten KI-Dossier", styles["h1"]))
story.append(Paragraph(
    "Diese Anleitung führt dich einmal komplett durch das Setup: Notion-Template, "
    "Automatisierung, API-Keys. Kein Coding-Wissen nötig — nur die Bereitschaft, "
    "dreimal Copy-Paste zu machen.",
    styles["body"],
))

story.append(eyebrow_heading("Bevor du startest", "Das brauchst du"))
story.extend(checklist([
    "Einen Notion-Account (kostenloser Plan reicht)",
    "Einen Anthropic API-Key (console.anthropic.com)",
    "Fünf Minuten für die Notion-Integration",
    "Entweder einen Make.com-/n8n-Account oder Python 3.10+ lokal",
]))

# --- Schritt 1 ---
story.append(eyebrow_heading("Schritt 1", "Notion-Template duplizieren"))
story.extend(numbered_list([
    "Öffne den Duplizieren-Link aus deiner Bestell-E-Mail.",
    "Klicke oben rechts auf <b>Duplicate</b> und wähle deinen Ziel-Workspace.",
    "Die Datenbank <b>„Account Dossiers“</b> liegt danach in deinem Workspace — "
    "verschiebe sie an die gewünschte Stelle (z.&nbsp;B. unter dein Sales-Hub).",
    "Öffne <b>Settings > Connections</b> in Notion und lege eine neue Integration an "
    "(oder nutze eine bestehende): <i>My Integrations > New Integration</i> — "
    "„Read/Update/Insert content“-Rechte reichen.",
    "Verbinde die Integration explizit mit der Datenbank „Account Dossiers“: "
    "Datenbank öffnen > „…“-Menü > <b>Connections</b> > deine Integration hinzufügen.",
    "Kopiere die <b>Database-ID</b> aus der Browser-URL der Datenbank (der 32-stellige "
    "Code direkt vor <b>?v=</b>). Du brauchst sie in Schritt 3.",
]))
story.append(note_box(
    "Schritt 5 wird am häufigsten übersprungen — ohne die explizite Verbindung kann "
    "die Automatisierung nicht schreiben, obwohl der API-Key korrekt ist."
))

# --- Schritt 2 ---
story.append(eyebrow_heading("Schritt 2", "Automatisierung anbinden"))
story.append(Paragraph(
    "Wähle einen der beiden Wege. Beide führen zum selben Ergebnis.", styles["body"],
))

story.append(Paragraph("Weg A — Python-Skript (pipeline.py), für Selbst-Hoster", styles["h3"]))
story.extend(numbered_list([
    "Entpacke den Ordner aus deinem Download.",
    "Installiere die Abhängigkeiten: <font name='DMSans-Bold'>pip install -r requirements.txt</font>",
    "Kopiere <font name='DMSans-Bold'>.env.example</font> zu <font name='DMSans-Bold'>.env</font>.",
    "Starte lokal zum Testen: <font name='DMSans-Bold'>uvicorn pipeline:app --reload</font>",
    "Für den produktiven Einsatz: als AWS-Lambda-Funktion deployen (Handler: "
    "<font name='DMSans-Bold'>pipeline.lambda_handler</font>) oder auf einem eigenen "
    "Server hinter einem Reverse Proxy betreiben.",
]))

story.append(Paragraph("Weg B — Make.com oder n8n, ohne eigenes Hosting", styles["h3"]))
story.extend(numbered_list([
    "Lege ein neues Szenario/Workflow an mit einem <b>Webhook-Trigger</b>.",
    "Füge ein <b>HTTP-Request-Modul</b> für den Website-Abruf hinzu: "
    "<font name='DMSans-Bold'>GET https://r.jina.ai/{domain}</font>",
    "Füge ein zweites <b>HTTP-Request-Modul</b> für die News hinzu: "
    "<font name='DMSans-Bold'>GET https://news.google.com/rss/search?q={firmenname}&amp;hl=de&amp;gl=DE&amp;ceid=DE:de</font>",
    "Füge ein <b>LLM-Modul</b> (Claude oder GPT) hinzu und füge den System-Prompt aus "
    "<font name='DMSans-Bold'>system-prompt.md</font> unverändert ein.",
    "Füge ein <b>Notion-Modul „Create a Database Item“</b> hinzu und verbinde es mit "
    "deinem Notion-Account aus Schritt 1.",
]))
story.append(Paragraph(
    "Ausführliche Modul-für-Modul-Beschreibung inkl. Feldmapping: siehe README.md im Blueprint-Ordner.",
    styles["body_muted"],
))

# --- Schritt 3 ---
story.append(eyebrow_heading("Schritt 3", "API-Keys hinterlegen"))

key_table = Table(
    [
        [Paragraph("Key", styles["table_head"]), Paragraph("Woher", styles["table_head"]), Paragraph("Wohin", styles["table_head"])],
        [
            Paragraph("ANTHROPIC_API_KEY", styles["table_cell_mono"]),
            Paragraph("console.anthropic.com > API Keys > Create Key", styles["table_cell"]),
            Paragraph(".env (Python) oder Connection im LLM-Modul (Make/n8n)", styles["table_cell"]),
        ],
        [
            Paragraph("NOTION_API_KEY", styles["table_cell_mono"]),
            Paragraph("Notion > My Integrations > Integration Token", styles["table_cell"]),
            Paragraph(".env (Python) oder Notion-Connection (Make/n8n)", styles["table_cell"]),
        ],
        [
            Paragraph("NOTION_DATABASE_ID", styles["table_cell_mono"]),
            Paragraph("Aus Schritt 1.6", styles["table_cell"]),
            Paragraph(".env (Python) oder direkt im Notion-Modul auswählen", styles["table_cell"]),
        ],
    ],
    colWidths=[4.8 * cm, 5.1 * cm, 6.2 * cm],
)
key_table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
    ("BACKGROUND", (0, 1), (-1, -1), WHITE),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, OFF_WHITE]),
    ("TOPPADDING", (0, 0), (-1, -1), 8),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ("LEFTPADDING", (0, 0), (-1, -1), 9),
    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
    ("LINEBELOW", (0, 0), (-1, 0), 2, TEAL),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
]))
story.append(key_table)
story.append(Spacer(1, 8))

story.append(note_box(
    "Sicherheitshinweis: Trage Keys ausschließlich in .env-Dateien oder die "
    "Connection-Verwaltung von Make.com/n8n ein — niemals in ein Notion-Textfeld, "
    "einen Screenshot oder eine Chat-Nachricht."
))

story.append(Paragraph("Erster Testlauf", styles["h3"]))
story.append(Paragraph(
    "Trage eine dir bekannte Firma ein (Name + Domain) und starte den Workflow "
    "einmal manuell. Prüfe:",
    styles["body"],
))
story.extend(checklist([
    "Ist die Branche plausibel klassifiziert?",
    "Wirkt der Pitch-Ansatz wie ein guter erster Entwurf — nicht wie Fantasie?",
    "Sind Datenlücken dort ausgewiesen, wo tatsächlich wenig öffentliche Information existiert?",
]))
story.append(Paragraph(
    "Wenn ja: Setup abgeschlossen. Wenn nein: Prüfe zuerst Schritt 1.5 (Connection) — "
    "das ist die häufigste Fehlerquelle.",
    styles["body"],
))

# --- Best Practices ---
story.append(eyebrow_heading("Für den Alltag", "Best Practices im Key Account Management"))

practices = [
    ("Wöchentlicher Rhythmus statt Dauerlauf.", "Reichere Accounts einmal pro Woche automatisch neu an, nicht bei jedem Klick — das spart API-Kosten und hält die Daten trotzdem aktuell genug für den Vertriebsalltag."),
    ("Manuelle Social Insights sind Chefsache.", "Trage LinkedIn-Beobachtungen selbst ein, kurz nachdem du sie gelesen hast — nicht drei Wochen später aus dem Gedächtnis."),
    ("Ein Datenlücken-Eintrag ist ein Signal, kein Fehler.", "Er zeigt dir genau, wo du selbst nachfassen solltest, statt dir eine erfundene Zahl unterzujubeln."),
    ("Der Icebreaker ist ein Entwurf, kein Skript.", "Bring ihn in deine eigenen Worte, bevor du ihn im Gespräch verwendest."),
    ("Vor dem Call reicht ein Zwei-Minuten-Review.", "Ein kurzer Blick auf News-Trigger und Pitch-Ansatz genügt — du musst das Dossier nicht bei jedem Gespräch neu durcharbeiten."),
]
for title, text in practices:
    story.append(Paragraph(f"<b>{title}</b> {text}", styles["body"]))

story.append(Spacer(1, 14))
story.append(Paragraph("Fragen zum Setup? kontakt@vertriebswerk.shop", styles["body_muted"]))

doc.build(story)
print(f"Erstellt: {OUTPUT_PATH}")

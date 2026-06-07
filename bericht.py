# -*- coding: utf-8 -*-
"""M5 – DigitalPakt-Verwendungsnachweis als PDF (reportlab).

Vier Abschnitte:
  1. Sachbericht (automatisch aus den Daten erzeugter Fließtext)
  2. Gesamtbelegliste (geförderte Geräte + Summe)
  3. Wartungs- und Support-Nachweis (Vorgänge im Zeitraum + Summen)
  4. Zweckbindungs-Übersicht (Inbetriebnahme + Zweckbindung bis, 5 Jahre)

Farben/Sprache wie im Web-Frontend (Navy/Teal, deutsche Zahlen).
"""
from datetime import date
from io import BytesIO
from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from formatting import de_date, de_menge, de_number, euro
from models import Geraet, Vorgang

NAVY = colors.HexColor("#1B3B5A")
TEAL = colors.HexColor("#2C6E7F")
LINE = colors.HexColor("#dde5ea")
MUTED = colors.HexColor("#5a6b76")
ZEBRA = colors.HexColor("#f4f6f8")

_ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=_ss["Title"], textColor=NAVY, fontSize=18,
                    spaceAfter=2, alignment=0)
H2 = ParagraphStyle("H2", parent=_ss["Heading2"], textColor=NAVY, fontSize=13,
                    spaceBefore=16, spaceAfter=6)
META = ParagraphStyle("Meta", parent=_ss["Normal"], textColor=MUTED, fontSize=9,
                      leading=13)
BODY = ParagraphStyle("Body", parent=_ss["Normal"], fontSize=10, leading=15,
                      alignment=TA_JUSTIFY, spaceAfter=8)
DECL = ParagraphStyle("Decl", parent=BODY, fontName="Helvetica-Bold",
                      textColor=NAVY, alignment=0, spaceBefore=4)
CELL = ParagraphStyle("Cell", parent=_ss["Normal"], fontSize=8, leading=11)
CELL_B = ParagraphStyle("CellB", parent=CELL, fontName="Helvetica-Bold")
NOTE = ParagraphStyle("Note", parent=_ss["Normal"], textColor=MUTED, fontSize=9,
                      leading=13, spaceBefore=2)


def _zeitraum_text(von: Optional[date], bis: Optional[date]) -> str:
    if von and bis:
        return f"vom {de_date(von)} bis {de_date(bis)}"
    if von:
        return f"ab {de_date(von)}"
    if bis:
        return f"bis {de_date(bis)}"
    return "über den gesamten erfassten Zeitraum"


def _table(data, col_widths, *, right_cols=(), total_row=False):
    """Einheitlich gestaltete Tabelle (Navy-Kopf, Zebra, dünne Linien)."""
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, NAVY),
    ]
    for c in right_cols:
        style.append(("ALIGN", (c, 1), (c, -1), "RIGHT"))
        style.append(("ALIGN", (c, 0), (c, 0), "RIGHT"))
    if total_row:
        last = len(data) - 1
        style += [
            ("BACKGROUND", (0, last), (-1, last), colors.HexColor("#eef3f5")),
            ("FONTNAME", (0, last), (-1, last), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, last), (-1, last), NAVY),
            ("LINEABOVE", (0, last), (-1, last), 0.8, NAVY),
        ]
    t.setStyle(TableStyle(style))
    return t


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 15 * mm, 192 * mm, 15 * mm)
    # Hinweis: vorbereitender Bericht, kein amtlicher Nachweis
    canvas.setFont("Helvetica-Oblique", 8)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(
        105 * mm, 10.5 * mm,
        "Vorbereitender Nachweisbericht – kein amtlicher Verwendungsnachweis")
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18 * mm, 6 * mm, "SchulIT · DigitalPakt-Verwendungsnachweis")
    canvas.drawRightString(192 * mm, 6 * mm, f"Seite {doc.page}")
    canvas.restoreState()


def build_bericht_pdf(*, schultraeger: str, schule: str,
                      von: Optional[date], bis: Optional[date],
                      foerderquelle: str, geraete: List[Geraet],
                      vorgaenge: List[Vorgang], geraet_namen: dict,
                      erstellt_am: date) -> bytes:
    foerder_label = foerderquelle or "alle Förderquellen"
    summe_anschaffung = sum(g.anschaffungskosten or 0 for g in geraete)
    n_wartung = sum(1 for v in vorgaenge if v.typ == "Wartung")
    n_stoerung = sum(1 for v in vorgaenge if v.typ == "Störung")
    summe_stunden = sum(v.aufwand_stunden for v in vorgaenge)
    summe_kosten = sum(v.kosten or 0 for v in vorgaenge)

    story = []

    # ---- Kopf ----
    story.append(Paragraph("DigitalPakt – Verwendungsnachweis", H1))
    story.append(Paragraph(
        f"{schule} · {schultraeger}<br/>"
        f"Förderquelle: <b>{foerder_label}</b> · Zeitraum: {_zeitraum_text(von, bis)}<br/>"
        f"Erstellt am: {de_date(erstellt_am)}", META))

    # ---- 1. Sachbericht ----
    story.append(Paragraph("1. Sachbericht", H2))
    story.append(Paragraph(
        f"Im Berichtszeitraum ({_zeitraum_text(von, bis)}) wurde am Standort "
        f"{schule} in Trägerschaft von {schultraeger} die im Rahmen der Förderung "
        f"„{foerder_label}“ beschaffte digitale Ausstattung betrieben und gewartet. "
        f"Der Bestand umfasst {len(geraete)} geförderte(s) Gerät(e) mit einem "
        f"Anschaffungsvolumen von insgesamt {euro(summe_anschaffung)}.", BODY))
    story.append(Paragraph(
        f"Im genannten Zeitraum wurden {len(vorgaenge)} Wartungs- und "
        f"Supportvorgänge dokumentiert, davon {n_wartung} planmäßige Wartung(en) "
        f"und {n_stoerung} Störungsbearbeitung(en). Der Gesamtaufwand für Betrieb "
        f"und Instandhaltung beträgt {de_number(summe_stunden)} Stunden; die "
        f"hierfür angefallenen Sach- und Dienstleistungskosten belaufen sich auf "
        f"{euro(summe_kosten)}. Die Maßnahmen dienten der Aufrechterhaltung des "
        f"bestimmungsgemäßen Betriebs der geförderten Geräte und damit unmittelbar "
        f"dem Förderzweck.", BODY))
    story.append(Paragraph(
        "Die Mittel wurden zweckentsprechend sowie wirtschaftlich und sparsam "
        "verwendet.", DECL))

    # ---- 2. Gesamtbelegliste ----
    story.append(Paragraph("2. Gesamtbelegliste", H2))
    if geraete:
        rows = [["Bezeichnung", "Inbetriebnahme", "Anschaffungskosten",
                 "Beleg-Nr.", "Förderquelle"]]
        for g in geraete:
            rows.append([
                Paragraph(g.bezeichnung, CELL),
                de_date(g.inbetriebnahme),
                euro(g.anschaffungskosten) if g.anschaffungskosten is not None else "–",
                g.beleg_nr or "–",
                Paragraph(g.foerderquelle or "–", CELL),
            ])
        rows.append(["", "", euro(summe_anschaffung), "Summe", ""])
        story.append(_table(rows, [52 * mm, 26 * mm, 34 * mm, 28 * mm, 34 * mm],
                            right_cols=(2,), total_row=True))
    else:
        story.append(Paragraph("Keine geförderten Geräte im gewählten Filter.", NOTE))

    # ---- 3. Wartungs- und Support-Nachweis ----
    story.append(Paragraph("3. Wartungs- und Support-Nachweis", H2))
    if vorgaenge:
        rows = [["Datum", "Gerät", "Typ", "Beschreibung", "Aufwand",
                 "Kostenart", "Kosten"]]
        for v in vorgaenge:
            aufwand = (f"{de_menge(v.aufwand)} {v.aufwand_einheit}"
                       if v.aufwand is not None else "–")
            rows.append([
                de_date(v.datum),
                Paragraph(geraet_namen.get(v.geraet_id, "–"), CELL),
                v.typ,
                Paragraph(v.beschreibung or "–", CELL),
                aufwand,
                Paragraph(v.kostenart or "–", CELL),
                euro(v.kosten) if v.kosten is not None else "–",
            ])
        rows.append(["", "", "", "", f"{de_number(summe_stunden)} h",
                     "Summe", euro(summe_kosten)])
        story.append(_table(
            rows, [18 * mm, 28 * mm, 15 * mm, 43 * mm, 19 * mm, 27 * mm, 24 * mm],
            right_cols=(6,), total_row=True))
        story.append(Paragraph(
            f"Gesamtaufwand: {de_number(summe_stunden)} Stunden · "
            f"Gesamtkosten: {euro(summe_kosten)}", NOTE))
    else:
        story.append(Paragraph("Im Zeitraum sind keine Vorgänge erfasst.", NOTE))

    # ---- 4. Zweckbindungs-Übersicht ----
    story.append(Paragraph("4. Zweckbindungs-Übersicht", H2))
    mit_inbetrieb = [g for g in geraete if g.inbetriebnahme]
    if mit_inbetrieb:
        rows = [["Bezeichnung", "Inbetriebnahme", "Zweckbindung bis (5 Jahre)"]]
        for g in mit_inbetrieb:
            rows.append([
                Paragraph(g.bezeichnung, CELL),
                de_date(g.inbetriebnahme),
                de_date(g.zweckbindung_bis),
            ])
        story.append(_table(rows, [86 * mm, 44 * mm, 44 * mm]))
        story.append(Paragraph(
            "Die Zweckbindung beträgt 5 Jahre ab Inbetriebnahme; in diesem Zeitraum "
            "sind die Geräte zweckentsprechend einzusetzen.", NOTE))
    else:
        story.append(Paragraph(
            "Für die geförderten Geräte ist kein Inbetriebnahmedatum hinterlegt.", NOTE))

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, title="DigitalPakt-Verwendungsnachweis",
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()

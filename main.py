# -*- coding: utf-8 -*-
"""SchulIT – M1 Skelett.

Geräte: Liste, Anlegen, Bearbeiten, Löschen.  Räume: Liste, Anlegen.
Server-gerendert (Jinja2), mobil-first. Starten:  uvicorn main:app --reload
"""
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional
from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from database import init_db, get_session
from models import (Geraet, Raum, Vorgang, GERAETE_TYPEN, STATUS_WERTE,
                    FOERDERQUELLEN, VORGANG_TYPEN, VORGANG_STATUS,
                    KOSTENARTEN, AUFWAND_EINHEITEN)
from formatting import euro as _euro, dezimal as _dezimal
from bericht import build_bericht_pdf


def _parse_float(wert: str):
    """Akzeptiert deutsche Eingabe: '1.234,56' -> 1234.56, '449' / '449.00' -> 449.0."""
    wert = (wert or "").strip()
    if not wert:
        return None
    if "," in wert:  # Komma = Dezimaltrenner, Punkt = Tausender
        wert = wert.replace(".", "").replace(",", ".")
    return float(wert)


def _parse_date(wert: str):
    wert = (wert or "").strip()
    return date.fromisoformat(wert) if wert else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="SchulIT", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
templates.env.filters["euro"] = _euro        # 1234.56 -> '1.234,56 €'
templates.env.filters["dezimal"] = _dezimal  # 1234.56 -> '1.234,56'


def _raum_namen(session: Session) -> dict:
    return {r.id: r.name for r in session.exec(select(Raum)).all()}


# ---------------- Geräte ----------------
@app.get("/")
def geraete_liste(request: Request, q: Optional[str] = None,
                  status: Optional[str] = None,
                  session: Session = Depends(get_session)):
    stmt = select(Geraet)
    geraete = session.exec(stmt).all()
    if q:
        ql = q.lower()
        geraete = [g for g in geraete if ql in g.bezeichnung.lower()
                   or (g.seriennummer or "").lower().find(ql) >= 0]
    if status:
        geraete = [g for g in geraete if g.status == status]
    geraete.sort(key=lambda g: g.bezeichnung.lower())
    return templates.TemplateResponse(request, "geraete_list.html", {
        "geraete": geraete,
        "raum_namen": _raum_namen(session),
        "status_werte": STATUS_WERTE, "q": q or "", "status_filter": status or "",
    })


@app.get("/geraete/neu")
def geraet_neu(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(request, "geraet_form.html", {
        "geraet": None,
        "raeume": session.exec(select(Raum)).all(),
        "typen": GERAETE_TYPEN, "status_werte": STATUS_WERTE,
        "foerderquellen": FOERDERQUELLEN,
    })


@app.post("/geraete/neu")
def geraet_anlegen(
    bezeichnung: str = Form(...), typ: str = Form("Tablet"),
    seriennummer: str = Form(""), raum_id: str = Form(""),
    status: str = Form("in Betrieb"), foerderquelle: str = Form(""),
    anschaffungskosten: str = Form(""), inbetriebnahme: str = Form(""),
    beleg_nr: str = Form(""), notiz: str = Form(""),
    session: Session = Depends(get_session)):
    g = Geraet(
        bezeichnung=bezeichnung.strip(), typ=typ,
        seriennummer=seriennummer.strip() or None,
        raum_id=int(raum_id) if raum_id else None, status=status,
        foerderquelle=foerderquelle or None,
        anschaffungskosten=_parse_float(anschaffungskosten),
        inbetriebnahme=_parse_date(inbetriebnahme),
        beleg_nr=beleg_nr.strip() or None,
        notiz=notiz.strip() or None,
    )
    session.add(g)
    session.commit()
    return RedirectResponse("/", status_code=303)


@app.get("/geraete/{geraet_id}/bearbeiten")
def geraet_bearbeiten(geraet_id: int, request: Request,
                      session: Session = Depends(get_session)):
    g = session.get(Geraet, geraet_id)
    if not g:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "geraet_form.html", {
        "geraet": g,
        "raeume": session.exec(select(Raum)).all(),
        "typen": GERAETE_TYPEN, "status_werte": STATUS_WERTE,
        "foerderquellen": FOERDERQUELLEN,
    })


@app.post("/geraete/{geraet_id}/bearbeiten")
def geraet_aktualisieren(
    geraet_id: int, bezeichnung: str = Form(...), typ: str = Form("Tablet"),
    seriennummer: str = Form(""), raum_id: str = Form(""),
    status: str = Form("in Betrieb"), foerderquelle: str = Form(""),
    anschaffungskosten: str = Form(""), inbetriebnahme: str = Form(""),
    beleg_nr: str = Form(""), notiz: str = Form(""),
    session: Session = Depends(get_session)):
    g = session.get(Geraet, geraet_id)
    if g:
        g.bezeichnung = bezeichnung.strip()
        g.typ = typ
        g.seriennummer = seriennummer.strip() or None
        g.raum_id = int(raum_id) if raum_id else None
        g.status = status
        g.foerderquelle = foerderquelle or None
        g.anschaffungskosten = _parse_float(anschaffungskosten)
        g.inbetriebnahme = _parse_date(inbetriebnahme)
        g.beleg_nr = beleg_nr.strip() or None
        g.notiz = notiz.strip() or None
        session.add(g)
        session.commit()
    return RedirectResponse("/", status_code=303)


@app.post("/geraete/{geraet_id}/loeschen")
def geraet_loeschen(geraet_id: int, session: Session = Depends(get_session)):
    g = session.get(Geraet, geraet_id)
    if g:
        # zugehörige Vorgänge mitlöschen
        for v in session.exec(select(Vorgang).where(Vorgang.geraet_id == geraet_id)).all():
            session.delete(v)
        session.delete(g)
        session.commit()
    return RedirectResponse("/", status_code=303)


@app.get("/geraete/{geraet_id}")
def geraet_detail(geraet_id: int, request: Request,
                  session: Session = Depends(get_session)):
    g = session.get(Geraet, geraet_id)
    if not g:
        return RedirectResponse("/", status_code=303)
    vorgaenge = session.exec(
        select(Vorgang).where(Vorgang.geraet_id == geraet_id)).all()
    vorgaenge.sort(key=lambda v: (v.datum, v.id or 0), reverse=True)
    return templates.TemplateResponse(request, "geraet_detail.html", {
        "geraet": g,
        "raum_namen": _raum_namen(session),
        "vorgaenge": vorgaenge,
    })


# ---------------- Vorgänge (M2) ----------------
@app.get("/vorgaenge")
def vorgaenge_liste(request: Request, typ: Optional[str] = None,
                    status: Optional[str] = None, von: Optional[str] = None,
                    bis: Optional[str] = None,
                    session: Session = Depends(get_session)):
    vorgaenge = session.exec(select(Vorgang)).all()
    if typ:
        vorgaenge = [v for v in vorgaenge if v.typ == typ]
    if status:
        vorgaenge = [v for v in vorgaenge if v.status == status]
    von_d, bis_d = _parse_date(von), _parse_date(bis)
    if von_d:
        vorgaenge = [v for v in vorgaenge if v.datum >= von_d]
    if bis_d:
        vorgaenge = [v for v in vorgaenge if v.datum <= bis_d]
    vorgaenge.sort(key=lambda v: (v.datum, v.id or 0), reverse=True)
    geraet_namen = {g.id: g.bezeichnung for g in session.exec(select(Geraet)).all()}
    return templates.TemplateResponse(request, "vorgaenge_list.html", {
        "vorgaenge": vorgaenge, "geraet_namen": geraet_namen,
        "vorgang_typen": VORGANG_TYPEN, "vorgang_status": VORGANG_STATUS,
        "typ_filter": typ or "", "status_filter": status or "",
        "von": von or "", "bis": bis or "",
    })


@app.get("/geraete/{geraet_id}/vorgaenge/neu")
def vorgang_neu(geraet_id: int, request: Request,
                session: Session = Depends(get_session)):
    g = session.get(Geraet, geraet_id)
    if not g:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "vorgang_form.html", {
        "geraet": g, "heute": date.today().isoformat(),
        "vorgang_typen": VORGANG_TYPEN, "vorgang_status": VORGANG_STATUS,
        "kostenarten": KOSTENARTEN, "aufwand_einheiten": AUFWAND_EINHEITEN,
    })


@app.post("/geraete/{geraet_id}/vorgaenge/neu")
def vorgang_anlegen(
    geraet_id: int, typ: str = Form("Wartung"), datum: str = Form(""),
    beschreibung: str = Form(""), aufwand: str = Form(""),
    aufwand_einheit: str = Form("Minuten"), bearbeiter: str = Form(""),
    kostenart: str = Form(""), kosten: str = Form(""), beleg_nr: str = Form(""),
    status: str = Form("neu"), session: Session = Depends(get_session)):
    g = session.get(Geraet, geraet_id)
    if not g:
        return RedirectResponse("/", status_code=303)
    v = Vorgang(
        geraet_id=geraet_id, typ=typ,
        datum=_parse_date(datum) or date.today(),
        beschreibung=beschreibung.strip(),
        aufwand=_parse_float(aufwand), aufwand_einheit=aufwand_einheit,
        bearbeiter=bearbeiter.strip() or None,
        kostenart=kostenart or None, kosten=_parse_float(kosten),
        beleg_nr=beleg_nr.strip() or None, status=status,
    )
    session.add(v)
    session.commit()
    return RedirectResponse(f"/geraete/{geraet_id}", status_code=303)


@app.post("/vorgaenge/{vorgang_id}/loeschen")
def vorgang_loeschen(vorgang_id: int, session: Session = Depends(get_session)):
    v = session.get(Vorgang, vorgang_id)
    ziel = f"/geraete/{v.geraet_id}" if v else "/vorgaenge"
    if v:
        session.delete(v)
        session.commit()
    return RedirectResponse(ziel, status_code=303)


# ---------------- Berichte (M5: DigitalPakt) ----------------
SCHULTRAEGER_DEFAULT = "Stadt Musterstadt"
SCHULE_DEFAULT = "Musterschule"


@app.get("/berichte")
def bericht_formular(request: Request):
    return templates.TemplateResponse(request, "berichte.html", {
        "foerderquellen": FOERDERQUELLEN,
        "schultraeger": SCHULTRAEGER_DEFAULT, "schule": SCHULE_DEFAULT,
    })


@app.post("/berichte")
def bericht_erstellen(
    von: str = Form(""), bis: str = Form(""), foerderquelle: str = Form(""),
    schultraeger: str = Form(SCHULTRAEGER_DEFAULT), schule: str = Form(SCHULE_DEFAULT),
    session: Session = Depends(get_session)):
    von_d, bis_d = _parse_date(von), _parse_date(bis)

    # Geförderte Geräte für Belegliste/Zweckbindung
    alle_geraete = session.exec(select(Geraet)).all()
    if foerderquelle:
        geraete = [g for g in alle_geraete if g.foerderquelle == foerderquelle]
    else:
        geraete = [g for g in alle_geraete if g.foerderquelle]
    geraete.sort(key=lambda g: g.bezeichnung.lower())
    geraet_namen = {g.id: g.bezeichnung for g in alle_geraete}

    # Vorgänge im Zeitraum (bei gewählter Förderquelle auf deren Geräte begrenzt)
    vorgaenge = session.exec(select(Vorgang)).all()
    if von_d:
        vorgaenge = [v for v in vorgaenge if v.datum >= von_d]
    if bis_d:
        vorgaenge = [v for v in vorgaenge if v.datum <= bis_d]
    if foerderquelle:
        ids = {g.id for g in geraete}
        vorgaenge = [v for v in vorgaenge if v.geraet_id in ids]
    vorgaenge.sort(key=lambda v: (v.datum, v.id or 0))

    pdf = build_bericht_pdf(
        schultraeger=schultraeger.strip() or SCHULTRAEGER_DEFAULT,
        schule=schule.strip() or SCHULE_DEFAULT,
        von=von_d, bis=bis_d, foerderquelle=foerderquelle,
        geraete=geraete, vorgaenge=vorgaenge, geraet_namen=geraet_namen,
        erstellt_am=date.today())
    dateiname = f"DigitalPakt-Verwendungsnachweis_{date.today().isoformat()}.pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{dateiname}"'})


# ---------------- Räume ----------------
@app.get("/raeume")
def raeume_liste(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(request, "raeume.html", {
        "raeume": session.exec(select(Raum)).all(),
    })


@app.post("/raeume")
def raum_anlegen(name: str = Form(...), beschreibung: str = Form(""),
                 session: Session = Depends(get_session)):
    if name.strip():
        session.add(Raum(name=name.strip(), beschreibung=beschreibung.strip() or None))
        session.commit()
    return RedirectResponse("/raeume", status_code=303)


@app.post("/raeume/{raum_id}/loeschen")
def raum_loeschen(raum_id: int, session: Session = Depends(get_session)):
    r = session.get(Raum, raum_id)
    if r:
        session.delete(r)
        session.commit()
    return RedirectResponse("/raeume", status_code=303)

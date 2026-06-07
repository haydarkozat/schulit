# -*- coding: utf-8 -*-
"""Datenbank-Setup. M1 nutzt SQLite (keine Konfiguration nötig).

Wechsel zu PostgreSQL später: nur DATABASE_URL ändern, z. B.
DATABASE_URL = "postgresql+psycopg://user:pass@localhost/schulit"
"""
import os
from sqlmodel import SQLModel, create_engine, Session, select
from datetime import date
from models import Raum, Geraet, Vorgang  # noqa: F401  (Vorgang -> create_all)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///schulit.db")
engine = create_engine(DATABASE_URL, echo=False,
                       connect_args={"check_same_thread": False}
                       if DATABASE_URL.startswith("sqlite") else {})


def get_session():
    with Session(engine) as session:
        yield session


def init_db():
    SQLModel.metadata.create_all(engine)
    # Demo-Daten nur beim ersten Start
    with Session(engine) as s:
        if s.exec(select(Raum)).first():
            return
        raeume = [Raum(name="Raum 112"), Raum(name="Raum 204"),
                  Raum(name="Lehrerzimmer"), Raum(name="Serverraum")]
        for r in raeume:
            s.add(r)
        s.commit()
        for r in raeume:
            s.refresh(r)
        geraete = [
            Geraet(bezeichnung="iPad 10,9\" #01", typ="Tablet",
                   seriennummer="DMP-001", raum_id=raeume[0].id,
                   status="in Betrieb", foerderquelle="DigitalPakt 2.0",
                   anschaffungskosten=449.0, inbetriebnahme=date(2026, 1, 28),
                   beleg_nr="RE-2026-0142"),
            Geraet(bezeichnung="Interaktives Display 86\"", typ="Interaktives Display",
                   seriennummer="ID-204", raum_id=raeume[1].id,
                   status="in Betrieb", foerderquelle="DigitalPakt 2.0",
                   anschaffungskosten=3290.0, inbetriebnahme=date(2026, 1, 12),
                   beleg_nr="RE-2026-0098"),
            Geraet(bezeichnung="Lehrer-Laptop #03", typ="Laptop",
                   seriennummer="LP-LZ-03", raum_id=raeume[2].id,
                   status="in Reparatur", foerderquelle="DigitalPakt 1.0",
                   anschaffungskosten=899.0, inbetriebnahme=date(2025, 9, 15),
                   beleg_nr="RE-2025-0771"),
        ]
        for g in geraete:
            s.add(g)
        s.commit()
        for g in geraete:
            s.refresh(g)
        ipad, display, laptop = geraete
        vorgaenge = [
            Vorgang(geraet_id=ipad.id, typ="Wartung", datum=date(2026, 2, 2),
                    beschreibung="iPadOS-Update, Reinigung, MDM-Profil geprüft",
                    aufwand=30, aufwand_einheit="Minuten", bearbeiter="A. Yilmaz",
                    kostenart="interne Stunden", kosten=0.0, status="erledigt"),
            Vorgang(geraet_id=display.id, typ="Störung", datum=date(2026, 3, 14),
                    beschreibung="Touch-Kalibrierung fehlerhaft, Firmware aktualisiert",
                    aufwand=1.5, aufwand_einheit="Stunden", bearbeiter="Hausmeister",
                    kostenart="interne Stunden", kosten=0.0, status="erledigt"),
            Vorgang(geraet_id=display.id, typ="Störung", datum=date(2026, 4, 20),
                    beschreibung="Defektes HDMI-Modul durch Dienstleister getauscht",
                    aufwand=2, aufwand_einheit="Stunden", bearbeiter="MediaTech GmbH",
                    kostenart="Ersatzteil", kosten=189.9, beleg_nr="RE-2026-0210",
                    status="erledigt"),
            Vorgang(geraet_id=laptop.id, typ="Störung", datum=date(2026, 5, 6),
                    beschreibung="Akku schwach, Austausch beauftragt",
                    aufwand=45, aufwand_einheit="Minuten", bearbeiter="MediaTech GmbH",
                    kostenart="externe Leistung", kosten=129.0, beleg_nr="RE-2026-0288",
                    status="in Bearbeitung"),
        ]
        for v in vorgaenge:
            s.add(v)
        s.commit()

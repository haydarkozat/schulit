# -*- coding: utf-8 -*-
"""Datenmodell – M1: Geräte + Räume.

Bewusst schlank gehalten. Förder-/Wartungsfelder sind bereits angelegt,
damit der spätere DigitalPakt-Layer (M5) ohne Migration aufsetzen kann.
"""
from datetime import date, datetime
from typing import Optional
from sqlmodel import SQLModel, Field


# ---- Auswahlwerte (in echt später konfigurierbar je Bundesland) ----
GERAETE_TYPEN = ["Tablet", "Laptop", "Interaktives Display", "Desktop-PC",
                 "Drucker", "Netzwerk (AP/Switch)", "Sonstiges"]

STATUS_WERTE = ["in Betrieb", "in Reparatur", "defekt", "ausgemustert"]

FOERDERQUELLEN = ["DigitalPakt 2.0", "DigitalPakt 1.0", "Eigenmittel", "Sonstiges"]

# ---- M2: Vorgänge (Wartung / Störung) ----
VORGANG_TYPEN = ["Wartung", "Störung"]
VORGANG_STATUS = ["neu", "in Bearbeitung", "erledigt"]
KOSTENARTEN = ["interne Stunden", "externe Leistung", "Ersatzteil"]
AUFWAND_EINHEITEN = ["Minuten", "Stunden"]


class Raum(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    beschreibung: Optional[str] = None


class Geraet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    bezeichnung: str
    typ: str = "Tablet"
    seriennummer: Optional[str] = None
    raum_id: Optional[int] = Field(default=None, foreign_key="raum.id")
    status: str = "in Betrieb"
    # --- Vorbereitung DigitalPakt-Layer (optional in M1) ---
    foerderquelle: Optional[str] = None
    anschaffungskosten: Optional[float] = None
    inbetriebnahme: Optional[date] = None
    beleg_nr: Optional[str] = None          # Rechnungs-/Belegnummer (M5-Nachweis)
    notiz: Optional[str] = None
    erstellt_am: datetime = Field(default_factory=datetime.utcnow)

    @property
    def zweckbindung_bis(self) -> Optional[date]:
        """5-Jahres-Zweckbindung – Grundlage für spätere Warnungen."""
        if self.inbetriebnahme:
            d = self.inbetriebnahme
            try:
                return d.replace(year=d.year + 5)
            except ValueError:  # 29.02
                return d.replace(year=d.year + 5, day=28)
        return None


class Vorgang(SQLModel, table=True):
    """M2: Wartungs-/Störungsvorgang an einem Gerät."""
    id: Optional[int] = Field(default=None, primary_key=True)
    geraet_id: int = Field(foreign_key="geraet.id", index=True)
    typ: str = "Wartung"                      # Wartung | Störung
    datum: date = Field(default_factory=date.today)
    beschreibung: str = ""
    aufwand: Optional[float] = None           # Menge ...
    aufwand_einheit: str = "Minuten"          # ... in Minuten | Stunden
    bearbeiter: Optional[str] = None
    kostenart: Optional[str] = None           # interne Stunden | externe Leistung | Ersatzteil
    kosten: Optional[float] = None
    beleg_nr: Optional[str] = None
    status: str = "neu"                       # neu | in Bearbeitung | erledigt
    erstellt_am: datetime = Field(default_factory=datetime.utcnow)

    @property
    def aufwand_stunden(self) -> float:
        """Aufwand normiert in Stunden – Basis für die Summen im Nachweis."""
        if self.aufwand is None:
            return 0.0
        return self.aufwand / 60 if self.aufwand_einheit == "Minuten" else self.aufwand

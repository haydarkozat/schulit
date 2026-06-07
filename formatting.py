# -*- coding: utf-8 -*-
"""Deutsche Zahlen-/Datumsformatierung – gemeinsam für Web (Jinja) und PDF.

Locale-unabhängig: formatiert mit Python und tauscht die Trennzeichen,
damit das Ergebnis serverunabhängig 1.234,56 € lautet.
"""
from datetime import date
from typing import Optional


def de_number(value, decimals: int = 2) -> str:
    """1234.56 -> '1.234,56' (Punkt = Tausender, Komma = Dezimal)."""
    s = f"{value:,.{decimals}f}"              # '1,234.56'
    return s.replace(",", "\0").replace(".", ",").replace("\0", ".")


def euro(value) -> str:
    return "–" if value is None else f"{de_number(value)} €"


def dezimal(value) -> str:
    return "" if value is None else de_number(value)


def de_menge(value) -> str:
    """Menge ohne erzwungene Nachkommastellen: 30 -> '30', 0.5 -> '0,5'."""
    if value is None:
        return ""
    if float(value).is_integer():
        return de_number(value, 0)
    return de_number(value, 2).rstrip("0").rstrip(",")


def de_date(value: Optional[date]) -> str:
    return value.strftime("%d.%m.%Y") if value else "–"

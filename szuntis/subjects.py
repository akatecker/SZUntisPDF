"""Fächerabkürzungen des Schulzentrums Ungargasse (Schuljahr 2026/27).

Automatisch erzeugt aus ``Faecherabkuerzungen_Ungargasse_Onepager.pdf``
(Abkürzungsverzeichnis der Schulinformation, S. 14-16, 111 Einträge).
Nicht von Hand bearbeiten - bei neuer PDF neu generieren.
"""

import re

#: Legende laut PDF-Kopf.
PRAEFIXE = {
    "UU_": "Unverbindliche Übung (Freifach)",
    "WP": "Werkstätte und Produktionstechnik",
    "CP": "Computerpraktikum",
    "ÜFA": "Übungsfirma",
}

FAECHER = {
    "AINF": "Angewandte Informatik",
    "AM": "Angewandte Mathematik",
    "AMEC": "Angewandte Mechatronik",
    "ANWA": "Angewandte Naturwissenschaften und Warenlehre",
    "B4A": "Badminton und Basketball",
    "BB2": "Business Behaviour",
    "BEC1": "Business English Certificate 1",
    "BESP": "Bewegung und Sport",
    "BET": "Betriebstechnik",
    "BETP_2": "Betriebstechnik und Projekte",
    "BPQM": "Business Training, Projektmanagement, Übungsfirma (ÜFA) und Case Studies",
    "BSPK": "Bewegung und Sport – Knaben",
    "BSPM": "Bewegung und Sport – Mädchen",
    "BTP_4": "Betriebspraxis",
    "BW": "Betriebswirtschaft",
    "BWRR": "Betriebswirtschaft, Wirtschaftliches Rechnen (WR), Rechnungswesen (RW)",
    "BWUF": "Betriebswirtschaftliche Übungen einschließlich Übungsfirma (ÜFA)",
    "CCIN_1": "Cloud Computing – Infrastructure",
    "COBF": "Coaching und Begabungsförderung",
    "CONJ": "Controlling + Jahresabschluss – Ausbildungsschwerpunkt",
    "COPR": "Computerpraktikum",
    "CRW": "Computerunterstütztes Rechnungswesen",
    "D": "Deutsch",
    "DESAP_4": "Design – Atelier Produktion",
    "DEST_1": "Design-Theorie",
    "DUK": "Deutsch und Kommunikation",
    "E1": "Englisch",
    "EBC3": "Europäischer Wirtschaftsführerschein (EBC*L)",
    "EBCO": "Englisch und Business Communication",
    "ENWS": "Englisch einschließlich Wirtschaftssprache",
    "ETAUTWP_4": "Elektro- und Automatisierungstechnik – Werkstätte und Produktionstechnik",
    "ETAUT_1": "Elektrotechnik und Automatisierungstechnik",
    "ETH": "Ethik",
    "FAT": "Fachtechnologie",
    "FELD": "Fachzeichnen, Entwurf und Lederdesign",
    "FET1WP_4": "Fertigungstechnik 1 – Werkstätte und Produktionstechnik",
    "FET1_1": "Fertigungstechnik 1",
    "FET2WP_3": "Fertigungstechnik 2 – Werkstätte und Produktionstechnik",
    "FET2_1": "Fertigungstechnik 2",
    "FRKM": "Französisch und Kommunikation",
    "FRWS": "Französisch einschließlich Wirtschaftssprache",
    "GEO": "Geografie",
    "GGP": "Geschichte, Geografie und Politische Bildung",
    "GUG": "Geschichte und Geografie",
    "INFI": "Informatik und Informationssysteme",
    "INSI_1": "Informatik und Informationssysteme",
    "INSY": "Informatik und Informationssysteme",
    "ITP2": "Informationstechnische Projekte",
    "ITSI_1": "IT-Sicherheit",
    "ITSM_1": "IT-Service Management",
    "IWK": "Internationale Wirtschafts- und Kulturräume",
    "KOBB": "Kundenorientierung und Verkauf",
    "KOP1": "Konstruktion und Projektmanagement",
    "LOSI_1": "Logistics Simulation",
    "MAM": "Mathematik und Angewandte Mathematik",
    "MDMMAP_4": "Modellbau und Mustermachen – Atelier und Produktion",
    "MDMM_2": "Modellbau und Mustermachen",
    "MEDT": "Medientechnik",
    "MME": "Mechanik und Maschinenelemente",
    "MT": "Mechanische Technologie",
    "MUL1": "Multimedia",
    "NW3": "Naturwissenschaften",
    "NWES": "Netzwerke und Embedded Software",
    "NWT1": "Netzwerktechnik",
    "NWT_4A": "Netzwerktechnik – Computerpraktikum",
    "OMAI": "Officemanagement und Angewandte Informatik",
    "OUNF": "Ökologisch orientierte Unternehmensführung – Ausbildungsschwerpunkt",
    "PBGW": "Politische Bildung und Geschichte",
    "PBSK": "Persönlichkeitsbildung und Soziale Kompetenz",
    "PBZG": "Politische Bildung und Zeitgeschichte",
    "PME3": "Peer-Group-Mediation",
    "PROM": "Projektatelier und Produktmanagement",
    "PSB3": "Psychologie (Betriebspsychologie)",
    "RE": "Religion evangelisch",
    "REHT": "Recht",
    "RISL": "Religion islamisch",
    "RK": "Religion römisch-katholisch",
    "RUKM": "Russisch und Kommunikation",
    "RUWS": "Russisch einschließlich Wirtschaftssprache",
    "SAP1": "Hersteller betriebswirtschaftlicher Standard-Software (SAP)",
    "SEIN_1": "Security – Infrastructure",
    "SEW": "Softwareentwicklung",
    "SMEN_1": "Smart Mechanical Engineering",
    "SOM1": "Sozialmanagement",
    "SOPK": "Soziale und Personale Kompetenz",
    "SPL": "Smart Production Lab",
    "SWP1": "Softwareentwicklung und Projektmanagement",
    "SWT": "Schweißtechnik",
    "SYT": "Systemtechnik",
    "SYTCP_4A": "Systemtechnik – Computerpraktikum",
    "TOW": "Technologie, Ökologie und Warenlehre",
    "UFW_1": "Unternehmensführung und Wirtschaftsrecht 1",
    "UFW_2": "Unternehmensführung und Wirtschaftsrecht 2",
    "UNCO": "Unternehmensrechnung und Controlling",
    "UNF": "Unternehmensführung",
    "UU_BOULD": "Unverbindliche Übung: Bouldern",
    "UU_KRaum": "Unverbindliche Übung: Kreativraum",
    "UU_LKM": "Unverbindliche Übung: Leistungskurs Mathematik",
    "UU_MTCNA": "Unverbindliche Übung: MikroTik Refresher Zertifikatskurs (MTCNA)",
    "UU_RHDS": "Unverbindliche Übung: Rhetorik und Darstellendes Spiel",
    "VOLL": "Volleyball",
    "VOW": "Volkswirtschaft",
    "VWRE": "Volkswirtschaft und Recht",
    "WBVB": "Werkzeug- und Vorrichtungsbau",
    "WBVBWP_4": "Werkzeug- und Vorrichtungsbau – Werkstätte und Produktionstechnik",
    "WIKU": "Wirtschafts- und Kulturräume (Geografie)",
    "WINF": "Wirtschaftsinformatik",
    "WIR_2": "Wirtschaft und Recht",
    "WIR_3": "Wirtschaft und Recht",
    "WPT_3": "Werkstätte und Produktionstechnik",
    "WPT_4": "Werkstätte und Produktionstechnik",
}


def _stamm(abk: str) -> str:
    """Entfernt Jahrgangs-/Variantenkennungen: ``FET2_1`` -> ``FET``, ``NW2`` -> ``NW``."""
    return re.sub(r"\d+$", "", re.sub(r"_\d+[A-Z]?$", "", abk))


# Stammform -> Bezeichnung, aber nur wo eindeutig (FET/NWT/UFW sind es nicht).
_gruppen: dict[str, set[str]] = {}
for _abk, _text in FAECHER.items():
    _gruppen.setdefault(_stamm(_abk), set()).add(_text)
_STAMM_INDEX = {k: next(iter(v)) for k, v in _gruppen.items() if len(v) == 1}


def klartext(abk: str, fallback: str = "") -> tuple[str, bool]:
    """Löst eine Fächerabkürzung in Klartext auf.

    Rückgabe ``(bezeichnung, exakt)``. ``exakt`` ist ``False``, wenn die
    Bezeichnung über die Stammform abgeleitet wurde (z. B. ``NW2`` aus ``NW3``)
    oder aus dem WebUntis-Langnamen stammt - die Oberfläche markiert das.
    """
    abk = (abk or "").strip()
    if not abk:
        return fallback or "", False
    if abk in FAECHER:
        return FAECHER[abk], True
    abgeleitet = _STAMM_INDEX.get(_stamm(abk))
    if abgeleitet:
        return abgeleitet, False
    if fallback:
        # WebUntis-Langnamen sind oft VERSALIEN oder fehlerhaft - wenigstens glätten.
        return (fallback.title() if fallback.isupper() else fallback), False
    return abk, False

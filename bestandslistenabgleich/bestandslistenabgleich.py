#!/usr/bin/env -S uv run
# -*- coding: utf-8 -*-
# vim: set autoindent smartindent softtabstop=4 tabstop=4 shiftwidth=4 expandtab:
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "isbnlib>=3.10",
#     "RapidFuzz>=3.13",
# ]
# ///
from __future__ import (
    print_function,
    with_statement,
    unicode_literals,
    division,
    absolute_import,
)

__author__ = "Oliver Schneider"
__copyright__ = "2024, 2025 Oliver Schneider (assarbad.net), under the terms of the UNLICENSE"
__version__ = "0.1.4"
__compatible__ = (
    (3, 12),
    (3, 13),
)
__doc__ = """
======================== 
 Bestandslistenabgleich
========================
"""
import argparse  # noqa: F401
import csv
import json
import logging
import os  # noqa: F401
import re
import sys
from collections.abc import Iterable
from contextlib import suppress
from functools import cache
from isbnlib import is_isbn13, is_isbn10, to_isbn13, canonical  # editions, meta, goom
from pathlib import Path
from rapidfuzz import fuzz, process, utils

# Checking for compatibility with Python version
if not sys.version_info[:2] in __compatible__:
    sys.exit(
        "Dieses Skript ist nur mit folgenden Pythonversionen kompatibel: %s" % (", ".join(["%d.%d" % (z[0], z[1]) for z in __compatible__]))
    )  # pragma: no cover


class ValidationError(ValueError): ...


def parse_args():
    """ """
    from argparse import ArgumentParser

    parser = ArgumentParser(description=Path(__file__).name)
    parser.add_argument(
        "--nologo",
        action="store_const",
        dest="nologo",
        const=True,
        help="Unterdrücke die Ausgabe des Logos dieses Skripts.",
    )
    parser.add_argument(
        "-u",
        "--url",
        dest="url",
        metavar="URL",
        help="URL zur Schule beim SBA-'Katalog'",
        default="https://sbakatalog.stadtbuecherei.frankfurt.de/A-F/Friedrich-Fr%C3%B6bel-Schule",
    )
    parser.add_argument(
        "-s",
        "--sba",
        action="store",
        dest="sbalist",
        metavar="SBALISTE",
        type=Path,
        help="Pfad zur SBA-Liste im JSON-Format, welche mit der 'sbasuche.py' erstellt wurde.",
        default=Path(__file__).parent.parent / "sbasuche/output.json",
    )
    parser.add_argument(
        action="store",
        dest="ownlist",
        metavar="EIGENELISTE",
        type=Path,
        help="Pfad zur CSV-Liste die aus unserem Excel-Sheet erstellt wurde.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        help="Setzen der Ausführlichkeit der Ausgaben (verbosity); kann mehrfach angegeben werden",
        default=0,
    )
    return parser.parse_args()


def setup_logging(verbosity: int):
    """\
    Initialisierung des Loggens in eine Datei und auf sys.stderr
    """
    # Ausführlichkeit wird als globale Variable verfügbar gemacht
    global verbose
    verbose = verbosity

    script_filename = Path(__file__).resolve()
    log_filename = f"{script_filename.stem}.log"
    log_filepath = script_filename.parent / log_filename

    logger = logging.getLogger(str(script_filename))
    logger.setLevel(logging.DEBUG)

    conlog = logging.StreamHandler(sys.stderr)
    filelog = logging.FileHandler(log_filepath)

    conloglvl = logging.WARNING
    if verbosity > 1:
        conloglvl = logging.DEBUG
    elif verbosity > 0:
        conloglvl = logging.INFO
    conlog.setLevel(conloglvl)
    filelog.setLevel(logging.DEBUG)

    confmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
    filefmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    conlog.setFormatter(confmt)
    filelog.setFormatter(filefmt)

    logger.addHandler(conlog)
    logger.addHandler(filelog)

    logger.debug("Logging initialisiert")
    return logger


def homoglyph_sanitize(inp):
    homoglyphs_mapping = {
        "\u2013": "-",  # En dash to hyphen
        "\u2014": "-",  # Em dash to hyphen
        "\u2010": "-",  # Hyphen to hyphen-minus
    }
    verbatim_input = inp
    for k, v in homoglyphs_mapping.items():
        inp = inp.replace(k, v)
    if inp != verbatim_input:
        global korrektur_count
        korrektur_count += 1
        log.info(f"Buchtitel wurde angepaßt (Homoglyphen): '{inp}'")
    return inp


LEERZEICHEN_VOR_SATZENDE = re.compile(r"\s+([!?])$")


def read_own_format(inp):
    # Sign,atur,Buchtitel,Verfasser,Zugang,,,Thema
    reader = csv.reader(inp, dialect="excel")
    mit_kürzel = re.compile(r"\([\w\(]+?\)$")  # beste Methode die wir bisher haben, es gibt ein paar Ausreißer
    sehen_staunen = re.compile(r"\s+\(sehen,\s*?staunen,\s*?wissen\)$", re.IGNORECASE)
    count = 0
    global korrektur_count
    korrektur_count = 0
    kartei = {}  # Karteinummer vorhanden und einmalig vorhanden
    waisen = []  # Keine Karteinummer
    duplikate = []  # Karteinummer gedoppelt
    for row in reader:
        if count > 0:
            buchtitel, verfasser, karteinummer = row[2].strip(), row[3].strip(), row[4].strip()
            # Homoglyphen behandeln, zur Verbesserung der Treffergenauigkeit (die Excel-Liste enthält da ein paar ... Artefakte)
            buchtitel, verfasser = homoglyph_sanitize(buchtitel), homoglyph_sanitize(verfasser)
            if m := sehen_staunen.search(buchtitel):
                buchtitel = re.sub(sehen_staunen, "", buchtitel)
                log.info(f"Buchtitel wurde angepaßt (sehen, staunen, wissen): '{buchtitel}'; war '{row[2]}'")
                korrektur_count += 1
            if m := mit_kürzel.search(buchtitel):
                buchtitel = buchtitel.split("(")[0].strip()
                log.info(f"Buchtitel wurde angepaßt (angehangene Systematik): '{buchtitel}'; war '{row[2]}'")
                korrektur_count += 1
            # Leerzeichen vor dem Satzende entfernen
            if LEERZEICHEN_VOR_SATZENDE.search(buchtitel):
                buchtitel = re.sub(LEERZEICHEN_VOR_SATZENDE, r"\1", buchtitel)
                log.info(f"Buchtitel wurde angepaßt (Satzende): '{buchtitel}'; war '{row[2]}'")
                korrektur_count += 1
            if karteinummer in {"?", ""}:
                log.debug(f"Ignoriere temporär ungültige Karteinummer: '{karteinummer}'.")
                waisen.append(
                    (
                        buchtitel,
                        verfasser,
                        karteinummer,
                    )
                )
            elif karteinummer in kartei:
                log.warning(
                    "Karteinummer %s taucht mehrfach in der Liste auf! [%s] vs. [%s]",
                    karteinummer,
                    repr(kartei[karteinummer]),
                    repr(
                        (
                            buchtitel,
                            verfasser,
                            karteinummer,
                        )
                    ),
                )
                duplikate.append(
                    (
                        buchtitel,
                        verfasser,
                        karteinummer,
                    )
                )
            else:
                kartei[karteinummer] = (
                    buchtitel,
                    verfasser,
                    karteinummer,
                )
        count += 1
    log.debug(f"{korrektur_count=}")
    return kartei, waisen, duplikate


@cache
def der_große_gleichmacher(inp):
    return utils.default_process(inp)


def abgleich_einzel_exemplare(katalog, kartei):
    global zugeordnete_karteinummern
    # Diese Fälle sind am einfachsten. Wir haben exakt ein Exemplar, welches wir eventuell zuordnen können
    einzel_exemplare = [x for x in katalog if len(x["copies"]) == 1]
    mehrfach_exemplare = [x for x in katalog if len(x["copies"]) != 1]
    assert len(einzel_exemplare) + len(mehrfach_exemplare) == len(katalog), "Beide Listen zusammen müssen exakt die Anzahl Elemente der Quellliste enthalten."
    gesamtzahl_exemplare = len(einzel_exemplare) + len(mehrfach_exemplare)
    log.debug(f"{len(kartei)=}")
    log.debug(f"{len(einzel_exemplare)=} (von {gesamtzahl_exemplare})")
    log.debug(f"{len(mehrfach_exemplare)=} (von {gesamtzahl_exemplare})")
    neuer_katalog = []
    zu_löschen = []
    # Exakte Treffer zuerst, damit die Liste der verbleibenden Kandidaten schön klein wird
    for buch in einzel_exemplare:
        for karteinummer, (buchtitel, verfasser, _) in kartei.items():
            if buch["title"].strip() != buch["title"]:
                log.debug("UNSTRIPPED (katalog): '%s'", buch["title"])
            if buchtitel.strip() != buchtitel:
                log.debug("UNSTRIPPED (kartei): '%s'", buchtitel)
            if der_große_gleichmacher(buch["title"]) == der_große_gleichmacher(buchtitel):
                del kartei[karteinummer]
                zu_löschen.append(buch)
                buch["karteinummern"] = [karteinummer]
                neuer_katalog.append(buch)
                zugeordnete_karteinummern[karteinummer] = buch
                break  # innere for-Schleife
    # Ein paar Debugausgaben
    log.debug(f"{len(zu_löschen)=}")
    log.debug(f"{len(katalog)=}")
    log.debug(f"{len(neuer_katalog)=}")
    # Katalogliste um jene Elemente bereinigen, die wir oben in neuer_katalog übernommen haben (dort inkl. Karteinummer)
    for eintrag in zu_löschen:
        katalog.remove(eintrag)
    assert len(einzel_exemplare) + len(mehrfach_exemplare) == len(neuer_katalog) + len(
        katalog
    ), "Beide Listen zusammen müssen exakt die Anzahl Elemente der Quellliste enthalten."
    log.debug(f"{len(katalog)=} (NACH LÖSCHUNG)")
    log.debug(f"{len(neuer_katalog)} + {len(katalog)} = {len(neuer_katalog)+len(katalog)}")
    # Nach der obigen Prüfung diese Elemente auch aus der Liste mit den Einzelexemplaren löschen
    for eintrag in zu_löschen:
        einzel_exemplare.remove(eintrag)
    log.debug(f"{len(einzel_exemplare)=} (NACH LÖSCHUNG)")
    zu_löschen = []  # Liste leeren, da wir hier quasi von vorn beginnen
    # Top-Treffer (>=95%) als nächste
    for attempt in range(5):
        kartei_titel = {k: x[0].strip() for k, x in kartei.items()}
        for buch in einzel_exemplare:
            for karteinummer, titel in kartei_titel.items():
                if karteinummer in zugeordnete_karteinummern:
                    log.debug(f"LOGIKFEHLER: {karteinummer=} ist bereits zugeordnet und taucht dennoch in der Liste auf.")
                if buch["title"].strip() != buch["title"]:
                    log.debug("UNSTRIPPED (katalog): '%s'", buch["title"])
                if buchtitel.strip() != buchtitel:
                    log.debug("UNSTRIPPED (kartei): '%s'", buchtitel)
            kandidaten = process.extract(buch["title"].strip(), kartei_titel, scorer=fuzz.WRatio, processor=der_große_gleichmacher, score_cutoff=95)
            if kandidaten and len(kandidaten) == 1:
                karteinummer = kandidaten[0][2]
                del kartei_titel[karteinummer]
                del kartei[karteinummer]
                zu_löschen.append(buch)
                buch["karteinummern"] = [karteinummer]
                neuer_katalog.append(buch)
                zugeordnete_karteinummern[karteinummer] = buch
                continue
        # Bereinigen
        for eintrag in zu_löschen:
            katalog.remove(eintrag)
            einzel_exemplare.remove(eintrag)
        for karteinummer in zugeordnete_karteinummern.keys():
            if karteinummer in kartei:
                del kartei[karteinummer]
        log.debug(f"#{attempt+1}: {len(zu_löschen)=} (beste Treffer >=95% mit gewichtetem Vergleich)")
        log.debug(f"#{attempt+1}: {len(kartei)=} (NACH LÖSCHUNG)")
        log.debug(f"#{attempt+1}: {len(neuer_katalog)=} (NACH LÖSCHUNG)")
        log.debug(f"#{attempt+1}: {len(einzel_exemplare)=} (NACH LÖSCHUNG)")
        log.debug(f"#{attempt+1}: {len(zugeordnete_karteinummern)=} (ENDRESULTAT)")
        if not zu_löschen:
            log.info(f"#{attempt+1}: keine neuen Treffer, verlasse Schleife")
            zu_löschen = []  # Liste leeren, da wir hier quasi von vorn beginnen
            break
        zu_löschen = []  # Liste leeren, da wir hier quasi von vorn beginnen
    # Plausible Treffer (>=80%) unter Zuhilfename der Autoreninformation
    kartei_titel = {k: x[0].strip() for k, x in kartei.items()}
    for buch in einzel_exemplare:
        for karteinummer, titel in kartei_titel.items():
            if karteinummer in zugeordnete_karteinummern:
                log.debug(f"LOGIKFEHLER: {karteinummer=} ist bereits zugeordnet und taucht dennoch in der Liste auf.")
            if buch["title"].strip() != buch["title"]:
                log.debug("UNSTRIPPED (katalog): '%s'", buch["title"])
            if buchtitel.strip() != buchtitel:
                log.debug("UNSTRIPPED (kartei): '%s'", buchtitel)
        kandidaten = process.extract(buch["title"].strip(), kartei_titel, scorer=fuzz.WRatio, processor=der_große_gleichmacher, score_cutoff=80)
        if kandidaten:
            # print(f"{len(kandidaten)=}")
            if len(kandidaten) == 1:
                kandidat = kandidaten[0]
                print(f"{kandidat=!r} -> '{buch["title"]}'")
        # if kandidaten and len(kandidaten) == 1:
        #     karteinummer = kandidaten[0][2]
        #     del kartei_titel[karteinummer]
        #     del kartei[karteinummer]
        #     zu_löschen.append(buch)
        #     buch["karteinummern"] = [karteinummer]
        #     neuer_katalog.append(buch)
        #     zugeordnete_karteinummern[karteinummer] = buch
        #     continue
    for eintrag in zu_löschen:
        katalog.remove(eintrag)
        einzel_exemplare.remove(eintrag)
    for karteinummer in zugeordnete_karteinummern.keys():
        if karteinummer in kartei:
            del kartei[karteinummer]
    # DEBUGGING
    outfile = Path(__file__).resolve().parent / "neu.json"
    with open(outfile, "w") as json_file:
        json.dump(neuer_katalog, json_file, allow_nan=False, ensure_ascii=False, sort_keys=True, indent=4)


def main(**kwargs):
    """ """
    global log
    log = setup_logging(kwargs.get("verbose", 0))
    sbalist = kwargs.get("sbalist", None)
    ownlist = kwargs.get("ownlist", None)
    katalog, kartei, waisen, duplikate = None, None, None, None
    with open(sbalist, "r") as json_file:
        katalog = json.load(json_file)
    print(f"{len(katalog)=}")
    with open(ownlist, "r") as owncsv:
        kartei, waisen, duplikate = read_own_format(owncsv)
    if katalog is None or not isinstance(katalog, Iterable):
        raise ValidationError("'katalog' (gelesen aus der JSON von sbasuche.py) ist ungültig.")
    if kartei is None or not isinstance(kartei, Iterable):
        raise ValidationError("'kartei' (gelesen aus unserer CSV-Liste) ist ungültig.")
    if waisen:
        log.warning("Habe %d verwaiste Einträge", 0 if waisen is None else len(waisen))
    if duplikate:
        log.warning("Habe %d Duplikat(e)", 0 if duplikate is None else len(duplikate))
    global zugeordnete_karteinummern
    zugeordnete_karteinummern = {}
    abgleich_einzel_exemplare(katalog, kartei)
    return 0


if __name__ == "__main__":
    args = parse_args()
    try:
        sys.exit(main(**vars(args)))
    except SystemExit:
        pass
    except ImportError:
        raise  # re-raise
    except RuntimeError:
        raise  # re-raise
    except Exception:
        print(__doc__)
        raise  # re-raise

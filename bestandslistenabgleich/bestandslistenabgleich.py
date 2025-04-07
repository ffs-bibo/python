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
__version__ = "0.1.1"
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
import sys
from collections.abc import Iterable
from isbnlib import is_isbn13, is_isbn10, to_isbn13, canonical  # editions, meta, goom
from pathlib import Path
from rapidfuzz import fuzz

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


def read_own_format(inp):
    # Sign,atur,Buchtitel,Verfasser,Zugang,,,Thema
    reader = csv.reader(inp, dialect="excel")
    count = 0
    kartei = {}  # Karteinummer vorhanden und einmalig vorhanden
    waisen = []  # Keine Karteinummer
    duplikate = []  # Karteinummer gedoppelt
    for row in reader:
        if count > 0:
            buchtitel, verfasser, karteinummer = row[2], row[3], row[4]
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
    return kartei, waisen, duplikate


def abgleich_einzel_exemplare(katalog, kartei):
    global zugeordnete_karteinummern
    # Diese Fälle sind am einfachsten. Wir haben exakt ein Exemplar, welches wir auch
    einzel_exemplare = [x for x in katalog if len(x["copies"]) == 1]
    print(f"{len(einzel_exemplare)=}")
    # print(f"{einzel_exemplare[0]!r}")
    count = 0
    exakte_treffer = {}
    top_treffer = {}
    gute_treffer = {}
    akzeptable_treffer = {}
    for buch in einzel_exemplare:
        highest_ratio = -1
        treffer = {}
        for karteinummer, (buchtitel, verfasser, _) in kartei.items():
            ratio = fuzz.token_set_ratio(buch["title"], buchtitel)
            if ratio > 80 and ratio >= highest_ratio:
                if ratio > highest_ratio:
                    treffer = {}
                highest_ratio = ratio
                treffer[karteinummer] = (highest_ratio, buchtitel, buch,)
        if treffer:
            if len(treffer) > 1:
                log.info("MEHRERE BEST-TREFFER: %d", len(treffer))
                for karteinummer, (highest_ratio, buchtitel, buch) in treffer.items():
                    log.info("[%s] '%s' (%2.2f) -> '%s'", karteinummer, buchtitel, highest_ratio, buch["title"])
                continue
            for karteinummer, (highest_ratio, buchtitel, buch) in treffer.items():
                if highest_ratio == 100:
                    exakte_treffer[karteinummer] = (
                        highest_ratio,
                        buchtitel,
                        buch,
                    )
                    del kartei[karteinummer]
                elif highest_ratio > 99:
                    top_treffer[karteinummer] = (
                        highest_ratio,
                        buchtitel,
                        buch,
                    )
                elif highest_ratio >= 90:
                    gute_treffer[karteinummer] = (
                        highest_ratio,
                        buchtitel,
                        buch,
                    )
                elif highest_ratio >= 80:
                    akzeptable_treffer[karteinummer] = (
                        highest_ratio,
                        buchtitel,
                        buch,
                    )
        count += 1
    print(f"{len(exakte_treffer)=}")
    print(f"{len(top_treffer)=}")
    print(f"{len(gute_treffer)=}")
    print(f"{len(akzeptable_treffer)=}")
    top_ratio = 100 * ((len(exakte_treffer) + len(top_treffer)) / len(einzel_exemplare))
    print(f"{top_ratio:2.2f} %")
    neuer_katalog = []

def main(**kwargs):
    """ """
    global log, cache
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

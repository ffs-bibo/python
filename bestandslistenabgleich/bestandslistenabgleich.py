#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: set autoindent smartindent softtabstop=4 tabstop=4 shiftwidth=4 expandtab:
from __future__ import (
    print_function,
    with_statement,
    unicode_literals,
    division,
    absolute_import,
)

__author__ = "Oliver Schneider"
__copyright__ = "2024 Oliver Schneider (assarbad.net), under the terms of the UNLICENSE"
__version__ = "0.1.0"
__compatible__ = (
    (3, 10),
    (3, 11),
    (3, 12),
)
__doc__ = """
=========
 PROGRAM
=========
"""
import argparse  # noqa: F401
import csv
import os  # noqa: F401
import sys
from isbnlib import is_isbn13, is_isbn10, to_isbn13, canonical  # editions, meta, goom
from pathlib import Path

# Checking for compatibility with Python version
if not sys.version_info[:2] in __compatible__:
    sys.exit(
        "This script is only compatible with the following Python versions: %s."
        % (", ".join(["%d.%d" % (z[0], z[1]) for z in __compatible__]))
    )  # pragma: no cover


def parse_args():
    """ """
    from argparse import ArgumentParser

    parser = ArgumentParser(description="PROGRAM")
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
        action="store",
        dest="sbalist",
        metavar="SBALISTE",
        type=Path,
        help="Pfad zur CSV-Liste die aus dem Excel-Sheet der SBA erstellt wurde.",
    )
    parser.add_argument(
        action="store",
        dest="ownlist",
        metavar="EIGENELISTE",
        type=Path,
        help="Pfad zur CSV-Liste die aus unserem Excel-Sheet erstellt wurde.",
    )
    return parser.parse_args()


def read_sba_format(inp):
    # "Systematik","Kurzanzeige","JahrAufl.","VerlagOrt","ISBN"
    reader = csv.reader(inp, dialect="excel")
    count = 0
    systematik = set()
    isbn_set = set()
    noisbn_list = []
    strange_isbns = []
    invalid_isbns = []
    for row in reader:
        if count > 0:
            systematik.add(row[0])
            if row[4].strip():
                isbn = canonical(row[4] if is_isbn13(row[4]) else to_isbn13(row[4]))
                if isbn:
                    print(f"{isbn}")
                    isbn_set.add(isbn)
                    if not isbn.startswith("9783"):
                        strange_isbns.append(isbn)
                else:
                    invalid_isbns.append(row)
            else:
                print(f"{row[1]}")
                noisbn_list.append(row[1:3])
        count += 1
    print(repr(systematik))
    print(f"{len(systematik)=}")
    print(f"{len(isbn_set)=}")
    print(f"{len(strange_isbns)=}")
    if len(strange_isbns) < 100:
        for entry in strange_isbns:
            print(f"Seltsame ISBN: {entry}")
            #print(f"{entry}")
    print(f"{len(noisbn_list)=}")
    if len(noisbn_list) < 100:
        for entry in noisbn_list:
            print(f"KEINE ISBN: {entry}")
            # print(f"{entry[0]}")
    if len(invalid_isbns) < 100:
        for row in invalid_isbns:
            print(f"Ungültige ISBN?: {row=}")


def read_own_format(inp):
    # Sign,atur,Buchtitel,Verfasser,Zugang,,,Thema
    reader = csv.reader(inp, dialect="excel")
    count = 0
    systematik = set()
    for row in reader:
        if count > 0:
            systematik.add(" ".join(row[0:2]))
        count += 1
    print(repr(systematik))
    print(f"{len(systematik)=}")


def main(**kwargs):
    """ """
    print(repr(kwargs))
    sbalist = kwargs.get("sbalist", None)
    ownlist = kwargs.get("ownlist", None)
    with open(sbalist, "r") as sbacsv:
        read_sba_format(sbacsv)
    # with open(ownlist, "r") as owncsv:
    #     read_own_format(owncsv)
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

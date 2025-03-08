#!/usr/bin/env -S uv run
# -*- coding: utf-8 -*-
# vim: set autoindent smartindent softtabstop=4 tabstop=4 shiftwidth=4 expandtab:
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "beautifulsoup4>=4.13",
#     "requests>=2.32",
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
__version__ = "0.1.0"
__compatible__ = (
    (3, 12),
    (3, 13),
)
__doc__ = """
========================
 SBA Suche
========================
"""
import argparse  # noqa: F401
import logging
import os  # noqa: F401
import re
import sys
import random
import requests
from bs4 import BeautifulSoup
from functools import cache
from pathlib import Path
from typing import Union, List
from urllib.parse import urlparse

# Checking for compatibility with Python version
if not sys.version_info[:2] in __compatible__:
    sys.exit(
        "Dieses Skript ist nur mit folgenden Pythonversionen kompatibel: %s" % (", ".join(["%d.%d" % (z[0], z[1]) for z in __compatible__]))
    )  # pragma: no cover


def parse_args():
    """\
    Argumente parsen
    """
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
        "-v",
        "--verbose",
        action="count",
        help="Setzen der Ausführlichkeit der Ausgaben (verbosity); kann mehrfach angegeben werden",
        default=0,
    )
    return parser.parse_args()


class SBASearch(object):
    __useragents = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:136.0) Gecko/20100101 Firefox/136.0",
        "Mozilla/5.0 (X11; Linux i686; rv:136.0) Gecko/20100101 Firefox/136.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0",
        "Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:136.0) Gecko/20100101 Firefox/136.0",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0",
        "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 OPR/117.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 OPR/117.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 OPR/117.0.0.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 OPR/117.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/131.0.2903.86",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/131.0.2903.86",
    )
    __book_default_value = "Buch"
    __branch_default_value = "Friedrich-Fröbel"
    __mediatype_default_value = 2  # 0 == alle, 1 == E-Medien, 2 == phys. Medien
    __searchuri_default_value = "/A-F/Friedrich-Fr%C3%B6bel-Schule"  # "/Mediensuche/Erweiterte-Suche" # "/Mediensuche/Einfache-Suche"

    def __init__(self, url: str):
        """\
        Initialisierer für unsere Hilfsklasse zur SBA-Suche.

        Hier werden u.a. bestimmte Annahmen überprüft und auch Elemente ermittelt, deren Inhalte irgendwie für die weiteren Abfragen relevant sind.
        """
        self.matching_item_re = re.compile(r"^(\d+?)\s+?Treffer$")
        self.session = requests.Session()
        # Die Standard HTTP-Header welche wir immer mitschicken wollen
        self.session.headers.update(
            {
                "User-Agent": random.choice(self.__useragents),  # beliebiger User-Agent
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate", # das sind jene die Requests von Haus aus unterstützt
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Priority": "u=0, i",
                "Pragma": "no-cache",
                "Cache-Control": "no-cache",
            }
        )
        log.debug("User-Agent: %s", self.session.headers["User-Agent"])
        self.initial_rsp = self.session.get(url)
        self.initial_soup = BeautifulSoup(self.initial_rsp.content, "html.parser")
        log.debug("%d Byte(s) mit HTTP-Code: %d", len(self.initial_rsp.content), self.initial_rsp.status_code)
        forms = self.initial_soup.find_all("form")
        # Wir sollten nur ein <form /> vorfinden
        assert len(forms) == 1, f"Es wurde nur ein Suchformular auf der Suchseite erwartet (sehe {len(forms)=})"
        self.searchform = forms[0]
        self.searchmethod = self.searchform.get("method", "get").lower()
        self.searchenctype = self.searchform.get("enctype", None)
        assert self.searchmethod in {"post"}, f"Es wird erwartet, daß das Formular per POST übertragen werden soll (habe {self.searchmethod=})."
        assert self.searchenctype in {"multipart/form-data"}, f"Habe bestimmte Kodierung für POST erwartet ({self.searchenctype=})."
        action_url = urlparse(self.initial_rsp.url)
        self.searchaction_url = f"{action_url.scheme}://{action_url.netloc}{self.__searchuri_default_value}"
        log.debug("Ermittelte URL für Suchanfragen: %s", self.searchaction_url)
        # Formularfelder
        self.searchbtn = self.find_searchform_singleton("input", {"type": "submit", "id": lambda x: x and x.endswith("_BtnSearch")})
        self.mediagroup_combobox = self.find_searchform_singleton("select", {"id": lambda x: x and x.endswith("_DdlMediaGroupValue")})
        self.login_link = self.find_searchform_singleton("a", {"id": lambda x: x and x.endswith("_loginLink")})
        self.branch = self.find_searchform_singleton("select", {"id": lambda x: x and x.endswith("_DdlBranchValue")})
        # Spezialfall versteckte Formularfelder (wir wollen alle, nicht nur ein bestimmtes)
        self.hidden_fields = self.searchform.find_all(["input"], attrs={"type": "hidden"})
        assert len(self.hidden_fields) > 1, f"Es wurden mehrere versteckte Formularfelder erwartet (sehe {len(self.hidden_fields)=})"
        # Medienarten sollten eine exakt vorbestimmte Menge sein, ansonsten verlangt das Skript nach einer Anpassung
        self.validate_mediatypes()
        self.mediatypes = self.get_mediatypes()  # benötigt für den Namen des entsprechenden Felds bei Suchanfragen
        # Auswahl für Mediengruppe bestimmen
        self.mediagroup_options = self.mediagroup_combobox.find_all("option", attrs={"value": self.__book_default_value})
        assert len(self.mediagroup_options) == 1, "Es wurde erwartet daß es die Mediengruppe '{self.__book_default_value}' gibt"
        # Auswahl für die Schulbibliothek bestimmen
        self.branch_selected = self.branch.find_all("option", attrs={"selected": "selected"})
        assert len(self.branch_selected) == 1, "Es wurde erwartet daß exakt eine Schulbibliothek vorausgewählt ist"
        self.branch_selected = self.branch_selected[0]
        log.debug("Schulbibliothek vorausgewählt: %s", self.branch_selected.get("value", "<keine>"))

    @cache
    def prepare_post_data(self):
        form_data = {}
        if not hasattr(self, "cached_form_data"):
            cached_form_data = {}
            mediagroup_name = self.mediagroup_combobox.get("name")
            mediagroup_value = self.mediagroup_combobox.get("value", self.__book_default_value)
            branch_name = self.branch.get("name")
            branch_value = self.branch_selected.get("value", self.__branch_default_value)
            mediatype_name = self.mediatypes[0].get("name")
            assert mediagroup_name, "Name des Feldes für die Mediengruppe konnte nicht ermittelt werden"
            assert branch_name, "Name des Feldes für die Zweigstelle (Schulbibliothek) konnte nicht ermittelt werden"
            assert mediatype_name, "Name des Feldes für die Medienart konnte nicht ermittelt werden"
            assert "$" in mediagroup_name and "$" in branch_name and "$" in mediatype_name, "'$' wurde in allen Feldnamen erwartet!"
            idx = mediagroup_name.rindex("$")
            prefix = mediagroup_name[: idx + 1]
            assert all(
                x.startswith(prefix) for x in {mediagroup_name, branch_name, mediatype_name}
            ), f"Alle Feldnamen müssen mit dem gleichen Präfix beginnen. Habe Präfix '{prefix}' ermittelt, aber folgende Namen bekommen: {mediagroup_name=!r}, {branch_name=!r}, {mediatype_name=!r}"
            cached_form_data[mediagroup_name] = mediagroup_value
            cached_form_data[branch_name] = branch_value
            cached_form_data[mediatype_name] = self.__mediatype_default_value  # nur physische Medien!
            cached_form_data.update(
                {
                    # Diese beiden scheinen ansonsten manchmal zu fehlen
                    "__EVENTTARGET": "",
                    "__EVENTARGUMENT": "",
                    # Die gehen eigentlich normalerweise in die URI
                    f"pagesize": "50",
                    f"top": "y",
                    # Wir schummeln hier ein wenig und hartkodieren einige der Formularfelder und deren Werte
                    f"{prefix}FirstSearchField": "Free",
                    f"{prefix}FirstSearchValue": "",
                    f"{prefix}SecondSearchOperator": "And",
                    f"{prefix}SecondSearchField": "Title",
                    f"{prefix}SecondSearchValue": "",
                    f"{prefix}ThirdSearchOperator": "And",
                    f"{prefix}ThirdSearchField": "Author",
                    f"{prefix}ThirdSearchValue": "",
                    f"{prefix}TxtNewAquisitionsPastDays": "",
                    f"{prefix}TbxProductionYearFrom": "",
                    f"{prefix}TbxProductionYearTo": "",
                    f"{prefix}BtnSearch": "Suchen",
                }
            )
            self.cached_form_data = cached_form_data
        form_data.update(self.cached_form_data)
        log.debug("Formularfelder (ohne versteckte): %r", form_data)
        # Zuletzt noch alle versteckten Formularfelder hinzufügen
        form_data.update(SBASearch.get_namevalue_dict(self.hidden_fields))
        return form_data

    def items(self):
        form_data = self.prepare_post_data()
        self.response = self.session.post(self.searchaction_url, data=form_data)
        if self.response.status_code >= 400:
            log.critical(f"POST gab Status {self.response.status_code} zurück (URL: {self.searchaction_url}).")
            return None
        # Hier sollten wir einen searchhash vorfinden
        assert "searchhash=OCLC_" in self.response.url, f"Es wurde erwartet einen 'searchhash' der mit 'OCLC_' beginnt in der URL für die Ergebnisliste vorzufinden."
        log.info("URL des Suchergebnisses: %s (Status: %d); Bytes: %d", self.response.url, self.response.status_code, len(self.response.content))
        soup = BeautifulSoup(self.response.content, "html.parser")
        item_total = soup.find_all("span", {"id": lambda x: x and x.endswith("_TotalItemsLabel")})
        assert len(item_total) == 2, f"Es wurde erwartet, daß die Gesamttrefferzahl exakt zweimal (oben + unten) in der Ergebnisliste auftaucht: {item_total!r}"
        item_total_text = item_total[0].get_text()
        item_total = None
        if match := self.matching_item_re.fullmatch(item_total_text):
            item_total = int(match.group(1), 10)
            log.info("Treffer: %d", item_total)
        else:
            # Das ist kein Riesenproblem, weil wir noch immer auf jeder Trefferseite "x von y" angezeigt bekommen sollten
            log.warning("Konnte nicht ermitteln wie viele Treffer es gab: %r", item_total_text)
        item_links = soup.find_all("a", {"id": lambda x: x and x.endswith("_LbtnShortDescriptionValue")})
        assert len(item_links) > 0, f"Es wurde mehr als ein Ergebnis in der Trefferliste erwartet: {len(item_links)=}"
        result_url = item_links[0].get("href", None)
        assert result_url is not None, f"Konnte das 'href'-Attribut des ersten Ergebnislinks nicht auslesen: {item_links[0]=!r}"
        assert "&detail=0&" in result_url, f"Der erste Ergebnislink sollte 'detail=0' beinhalten: {result_url=!r}"
        assert "searchhash=OCLC_" in result_url, f"Es wurde erwartet einen 'searchhash' der mit 'OCLC_' beginnt im ersten Ergebnislink vorzufinden."
        template_url = result_url.replace("&detail=0&", "&detail={item_index}&")
        log.info("Die ermittelte _generische_ URL für Ergebnisdetails lautet: %s", template_url)
        # TODO/FIXME: falls wir in dieses Problem laufen, sollten wir die Trefferanzahl halt später ermitteln

        def get_detail_url():
            for idx in range(0, item_total):
                yield template_url.format(item_index=idx)

        return get_detail_url()


    @staticmethod
    def get_values(bsresultset):
        """\
        Nimmt ein BS4 ResultSet und ermittelt die Werte der 'value'-Attribute, pro Element.
        """
        return [elem.get("value") for elem in bsresultset]

    @staticmethod
    def get_namevalue_dict(bsresultset):
        """\
        Nimmt ein BS4 ResultSet und erstellt ein Dictionary aus den 'name'- und 'value'-Attributen, pro Element.
        """
        return {elem.get("name"): elem.get("value", "") for elem in bsresultset}

    @cache
    def get_mediatypes(self):
        mediatypes = self.searchform.find_all(
            "input", attrs={"id": lambda x: x and "_RbMediaTypeList_" in x, "name": lambda x: x and x.endswith("RbMediaTypeList")}
        )
        assert len(mediatypes) == 3, f"Habe exakt drei Medienarten erwartet (sehe {mediatypes=})"
        return mediatypes

    def validate_mediatypes(self):
        """\
        Stellt sicher, daß die im Formular vorgefundenen Medienarten mit unseren Annahmen übereinstimmen.
        """
        mediatypes = self.get_mediatypes()
        # Erwartet: 0 == alle, 1 == E-Medien, 2 == phys. Medien
        mediatypes = SBASearch.get_values(mediatypes)
        mediatypes = [int(m, 10) for m in mediatypes]
        expected = {0, 1, 2}
        assert set(mediatypes) == expected, f"Habe eine genaue Menge von Medienarten erwartet ({expected}), sehe: {mediatypes}"

    def find_searchform_singleton(self, xmltype: Union[str, List[str]], attrs: dict):
        """\
        Sucht innerhalb des ermittelten Suchformulars (self.searchform) Elemente von denen es jeweils nur exakt eines geben darf.
        """
        elems = self.searchform.find_all(xmltype, attrs=attrs)
        assert len(elems) == 1, f"Es wurde nur ein Element zurückerwartet (habe {len(elems)=}, {xmltype!r}, {attrs=})"
        return elems[0] if len(elems) == 1 else None


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


def main(**kwargs):
    """\
    Die Hauptfunktion
    """
    global log
    log = setup_logging(kwargs.get("verbose", 0))
    url = kwargs.get("url", None)
    assert url is not None, f"Die Einstiegs-URL kann nicht 'nichts' (None) sein."
    search = SBASearch(url)
    for detail_url in search.items():
        print(detail_url)


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

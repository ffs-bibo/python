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
__version__ = "0.2.3"
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
import json
import os  # noqa: F401
import re
import sys
import random
import requests
import time
from bs4 import BeautifulSoup
from contextlib import suppress
from functools import cache
from pathlib import Path
from typing import Union, List, Optional
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
        "-c",
        "--cache",
        action="store_const",
        dest="cache",
        const=True,
        help="Unterdrücke erneute Abfrage der Online-Quelle der SBA. Stattdessen wird der Cache bemüht (sofern verfügbar).",
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
        "-o",
        "--output",
        dest="outfile",
        metavar="JSONFILE",
        help="Pfad zu einer JSON-Datei in welche die Ausgabe geschrieben werden soll",
        default=Path(__file__).resolve().parent / "output.json",
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


class ValidationError(ValueError): ...


class SBARequestError(RuntimeError): ...


class SBALogicError(RuntimeError): ...


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

    def __init__(self, url: str, cache: bool):
        """\
        Initialisierer für unsere Hilfsklasse zur SBA-Suche.

        Hier werden u.a. bestimmte Annahmen überprüft und auch Elemente ermittelt, deren Inhalte irgendwie für die weiteren Abfragen relevant sind.
        """
        self.cache = cache
        if self.cache:
            return
        self.matching_item_re = re.compile(r"^(\d+?)\s+?Treffer$")
        self.session = requests.Session()
        # Die Standard HTTP-Header welche wir immer mitschicken wollen
        self.session.headers.update(
            {
                "User-Agent": random.choice(self.__useragents),  # beliebiger User-Agent
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",  # das sind jene die Requests von Haus aus unterstützt
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
        self.initial_soup = BeautifulSoup(self.initial_rsp.text, "html.parser")
        log.debug("%d Byte(s) mit HTTP-Code: %d", len(self.initial_rsp.text), self.initial_rsp.status_code)
        if self.initial_rsp.status_code not in range(100, 400):
            log.critical("%d Byte(s) mit HTTP-Code: %d", len(self.initial_rsp.text), self.initial_rsp.status_code)
            raise SBARequestError(f"HTTP-Status[GET]: {self.initial_rsp.status_code} (URL: {url})")
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

    def cached_items(self):
        cache_basepath = self.get_cache_basepath()
        cached_searchhashes = [d for d in cache_basepath.iterdir() if d.is_dir() and d.stem.startswith("OCLC_")]
        if not cached_searchhashes:
            raise SBALogicError(f"Im Cache-Pfad ({self.get_cache_basepath()}) wurde kein Verzeichnis mit dem Namen eines Suchhashes gefunden.")
        newest_cache_dir = sorted(cached_searchhashes, key=lambda d: d.stat().st_mtime)[-1]
        cache_file_list = sorted([cache_file for cache_file in newest_cache_dir.glob("detail_????.html")])
        assert cache_file_list, f"Es wurde kein gültiges bereits zwischengespeichertes Verzeichnis gefunden (habe versucht: {newest_cache_dir})."
        assert (
            cache_file_list[0].name == "detail_0000.html"
        ), f"Der erste Eintrag der Cache-List hätte 'detail_0000.html' sein sollen ({len(cache_file_list)=})."

        def get_detail_url():
            for idx, cache_file in enumerate(cache_file_list):
                yield idx, cache_file

        return get_detail_url()

    def items(self):
        if self.cache:  # sidestep the online stuff
            return self.cached_items()
        form_data = self.prepare_post_data()
        self.response = self.session.post(self.searchaction_url, data=form_data)
        if self.response.status_code >= 300:  # Umleitungen aus dem 300er-Bereich sollten hier nicht auftauchen, weil die Requests normalerweise befolgt
            log.critical(f"POST gab Status {self.response.status_code} zurück (URL: {self.searchaction_url}).")
            raise SBARequestError(f"HTTP-Status[POST]: {self.response.status_code} (URL: {self.searchaction_url})")
        # Hier sollten wir einen searchhash vorfinden
        assert (
            "searchhash=OCLC_" in self.response.url
        ), f"Es wurde erwartet einen 'searchhash' der mit 'OCLC_' beginnt in der URL für die Ergebnisliste vorzufinden."
        log.info("URL des Suchergebnisses: %s (Status: %d); Bytes: %d", self.response.url, self.response.status_code, len(self.response.text))
        soup = BeautifulSoup(self.response.text, "html.parser")
        item_total = soup.find_all("span", {"id": lambda x: x and x.endswith("_TotalItemsLabel")})
        assert len(item_total) == 2, f"Es wurde erwartet, daß die Gesamttrefferzahl exakt zweimal (oben + unten) in der Ergebnisliste auftaucht: {item_total!r}"
        item_total_text = item_total[0].get_text()
        item_total = None
        if match := self.matching_item_re.fullmatch(item_total_text):
            item_total = int(match.group(1), 10)
            log.info("Treffer: %d", item_total)
        else:
            log.critical("Konnte nicht ermitteln wie viele Treffer es gab: %r", item_total_text)
            raise SBALogicError(f"Trefferzahl nicht ermittelbar: {item_total_text!r}")
        item_links = soup.find_all("a", {"id": lambda x: x and x.endswith("_LbtnShortDescriptionValue")})
        assert len(item_links) > 0, f"Es wurde mehr als ein Ergebnis in der Trefferliste erwartet: {len(item_links)=}"
        result_url = item_links[0].get("href", None)
        assert result_url is not None, f"Konnte das 'href'-Attribut des ersten Ergebnislinks nicht auslesen: {item_links[0]=!r}"
        assert "&detail=0&" in result_url, f"Der erste Ergebnislink sollte 'detail=0' beinhalten: {result_url=!r}"
        assert "searchhash=OCLC_" in result_url, f"Es wurde erwartet einen 'searchhash' der mit 'OCLC_' beginnt im ersten Ergebnislink vorzufinden."
        template_url = result_url.replace("&detail=0&", "&detail={item_index}&")
        log.info("Die ermittelte _generische_ URL für Ergebnisdetails lautet: %s", template_url)

        def get_detail_url():
            for idx in range(0, item_total):
                yield idx, template_url.format(item_index=idx)

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

    @cache
    def get_cache_basepath(self) -> Path:
        retval = Path(__file__).resolve().parent / "cache"
        return retval

    @cache
    def get_cache_path(self, searchhash: str) -> Path:
        retval = self.get_cache_basepath() / searchhash
        log.info("Cache-Pfad = %s", retval)
        return retval

    @cache
    def get_cached_content(self, idx: int, url: Union[str, Path]):
        force_cache = not isinstance(url, str)
        if not force_cache:
            parsed_url = urlparse(url)
            assert parsed_url.query, f"Die Query in der URL hätte nicht leer sein dürfen! ({url=})"
            assert "&" in parsed_url.query, f"Es wurde ein '&' in der Query ({url=}) erwartet"
            assert "searchhash=" in parsed_url.query, f"Es wurde ein 'searchhash=' in der URL ({url=}) erwartet"
            searchhash = [x for x in url.split("?")[1].split("&") if x.startswith("searchhash=")][0].split("=")[1]
            cache_path = self.get_cache_path(searchhash)
            cache_path.mkdir(parents=True, exist_ok=True)
            cache_filepath = cache_path / f"detail_{idx:04d}.html"
        else:
            cache_filepath = url
        with suppress(FileNotFoundError):
            with open(cache_filepath, "r") as cache_file:
                log.debug("Cache-Treffer: #%d -> %s", idx, url)
                return cache_file.read()
        if force_cache:
            log.critical(f"Es war nicht möglich den Cache für die angefragte Datei auszulesen ({idx=}; {cache_filepath=}).")
            raise SBALogicError(f"Es war nicht möglich den Cache für die angefragte Datei auszulesen ({idx=}; {cache_filepath=}).")
        # Wir machen das _vor_ dem nächsten with-Bereich, damit wir möglichst keine leeren Dateien erzeugen
        details = self.session.get(url)
        if details.status_code >= 300:  # Umleitungen aus dem 300er-Bereich sollten hier nicht auftauchen, weil die Requests normalerweise befolgt
            log.critical(f"GET gab Status {details.status_code} zurück (URL: {url}).")
            raise SBARequestError(f"HTTP-Status[GET]: {details.status_code} (URL: {url})")
        with open(cache_filepath, "w") as cache_file:
            cache_file.write(details.text)
        delay = random.choice(range(250, 1000))  # in Millisekunden
        log.debug("Cache-Fehlschlag: #%d -> %s (Verzögerung %d ms})", idx, url, delay)
        time.sleep(delay / 1000)
        return details.text

    def get_details_soup(self, idx: int, url: str):
        details = self.get_cached_content(idx, url)
        return BeautifulSoup(details, "html.parser")


class SBABookDetails(object):
    _known_attributes = {
        "authors": lambda x: isinstance(x, tuple),  # 0..∞
        "title": lambda x: isinstance(x, str) and x,  # 1
        "excerpt": lambda x: x is None or (isinstance(x, str) and x),  # kann leer sein!
        "responsibility": lambda x: isinstance(x, tuple),  # 0..∞?
        "publish_year": lambda x: isinstance(x, str) and x,  # 1
        "publisher": lambda x: isinstance(x, tuple),  # 0..1
        "systematics": lambda x: isinstance(x, tuple) and len(x) > 0 and all(isinstance(e, str) for e in x),  # 1..∞?
        "subject_type": lambda x: isinstance(x, tuple) and all(isinstance(e, str) for e in x),  # 0..∞?
        "isbn": lambda x: isinstance(x, tuple) and len(x) in {0, 1},  # 0..1
        "description": lambda x: isinstance(x, str) and x,  # 1
        "match_entry": lambda x: isinstance(x, int) or x is None,
        "match_index": lambda x: isinstance(x, int) or x is None,
        "match_total": lambda x: isinstance(x, int) or x is None,
        "copies": lambda x: isinstance(x, list) and len(x) > 0 and all(isinstance(e, dict) for e in x),  # 1..∞?
    }

    def __init__(self, soup):
        self.soup = soup
        self._attributes = {}
        self._known_attributes = SBABookDetails._known_attributes
        self.valid_copy_cols = {
            (
                "Schulbibliothek",
                "Standorte",
                "Status",
                "Rückgabedatum",
            ),
            (
                # Sonderfall: https://sbakatalog.stadtbuecherei.frankfurt.de/Mediensuche/Einfache-Suche?searchhash=OCLC_a15e4d46661d4e3fdcbb4e23f983fb9a03fa8e9f&top=y&page=157&detail=1562&zwst=Friedrich-Fr%c3%b6bel
                "Aktion",
                "Schulbibliothek",
                "Standorte",
                "Status",
                "Rückgabedatum",
            ),
        }
        self.__parse()

    @cache
    def __getattr__(self, name):
        if name not in self._known_attributes:
            raise AttributeError(f"'{self.__class__.__name__}' object has no known attribute '{name}'")
        if name in self._attributes:
            return self._attributes[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    @cache
    def __dir__(self):
        return list(self._known_attributes.keys()) + super().__dir__()

    @property
    @cache
    def prefix(self):
        anyelem = self.soup.find_all("div", {"id": lambda x: x and x.endswith("_MainView_UcDetailView_CatalogueDetailView")})
        if len(anyelem) != 1:
            raise ValidationError(f"Es wird erwartet daß nur ein Element mit der gesuchten ID existiert ({anyelem=!r})")
        anyelem = anyelem[0]
        anyid = anyelem.get("id")
        idre = re.compile(r"^(dnn_ctr\d+?)_")
        if match := idre.match(anyid):
            return match.group(1)
        log.critical("Die ID (%r) stimmte nicht mit der Regex (%r) überein", anyid, idre.pattern)
        log.debug("Präfix für IDs: %s", prefix)
        raise SBALogicError(f"Die ID ({anyid!r}) stimmte nicht mit der Regex ({idre.pattern!r}) überein")

    def __parse(self):
        soup = self.soup
        prefix = self.prefix
        # Vorbelegungen für Werte die mglw. nicht vorhanden sind
        self._attributes["match_entry"] = None
        self._attributes["match_index"] = None
        self._attributes["match_total"] = None
        self._attributes["number_copies"] = 0
        self._attributes["excerpt"] = None
        # Autoren/Beteiligte (0..∞)
        self._attributes["authors"] = tuple(
            x.get_text()
            for x in self.find_all(
                attrs={
                    "id": re.compile(rf"^{prefix}_MainView_UcDetailView_ucCatalogueDetailView_LVAuthorValue_LinkAuthor_[0-9]+$"),
                    "aria-describedby": f"{prefix}_MainView_UcDetailView_ucCatalogueDetailView_ScreenReaderAuthorLink",
                }
            )
            if x.get_text().strip()
        )
        # Buchtitel (1)
        title = [x.get("content").strip() for x in self.find_all(xmltype="meta", attrs={"property": f"og:title", "content": lambda x: x})]
        if len(title) != 1:
            raise ValidationError(f"Nur ein Buchtitel wurde erwartet (habe {len(title)=})!")
        if not title:
            raise ValidationError(f"Buchtitel darf nicht leer sein ({title=!r})!")
        self._attributes["title"] = title[0]
        # Exzerpt/Inhaltsangabe (kann leer sein!)
        excerpt = tuple(x.get("content") for x in self.find_all(attrs={"property": f"og:description", "content": lambda x: x}))
        if excerpt:
            if len(excerpt) != 1:
                raise ValidationError(f"Nur eine Inhaltsangabe wurde erwartet (habe {len(excerpt)=})!")
            self._attributes["excerpt"] = excerpt[0]
        # Von/Mit (0..∞?)
        self._attributes["responsibility"] = tuple(
            x.get_text()
            for x in self.find_all(
                attrs={
                    "id": f"{prefix}_MainView_UcDetailView_ucCatalogueDetailView_LblStatementOfResponsibilityValue",
                }
            )
            if x.get_text().strip()
        )
        # Erscheinungsjahr (1)
        publish_year = tuple(
            x.get_text()
            for x in self.find_all(
                attrs={
                    "id": f"{prefix}_MainView_UcDetailView_ucCatalogueDetailView_LblProductionYearValue",
                }
            )
            if x.get_text().strip()
        )
        if len(publish_year) != 1:
            raise ValidationError(f"Es wurde ein Erscheinungsjahr erwartet (habe {len(publish_year)=}).")
        self._attributes["publish_year"] = publish_year[0]
        # Ort, Verlag/Herausgeber/Hersteller (0..1)
        self._attributes["publisher"] = tuple(
            x.get_text()
            for x in self.find_all(
                attrs={
                    "id": f"{prefix}_MainView_UcDetailView_ucCatalogueDetailView_LblManufacturerValue",
                }
            )
            if x.get_text().strip()
        )
        # Systematiken (1..∞?)
        systematics = tuple(
            x.get_text().strip()
            for x in self.find_all(
                attrs={
                    "id": re.compile(rf"^{prefix}_MainView_UcDetailView_ucCatalogueDetailView_LVSystematicValue_LinkSystematic_[0-9]+$"),
                    "aria-describedby": f"{prefix}_MainView_UcDetailView_ucCatalogueDetailView_ScreenReaderSystematicLink",
                }
            )
            if x.get_text().strip()
        )
        if not systematics:
            raise ValidationError(f"Es wurde mindestens eine Systematik erwartet (habe {len(systematics)=}).")
        self._attributes["systematics"] = systematics
        # Interessenkreis (0..∞?)
        self._attributes["subject_type"] = tuple(
            x.get_text().strip()
            for x in self.find_all(
                attrs={
                    "id": re.compile(rf"^{prefix}_MainView_UcDetailView_ucCatalogueDetailView_LVSubjectTypeValue_LinkSubjectType_[0-9]+$"),
                    "aria-describedby": f"{prefix}_MainView_UcDetailView_ucCatalogueDetailView_ScreenReaderSubjectType",
                }
            )
            if x.get_text().strip()
        )
        # ISBN (0..1)
        self._attributes["isbn"] = tuple(
            x.get_text().strip()
            for x in self.find_all(
                attrs={
                    "id": f"{prefix}_MainView_UcDetailView_ucCatalogueDetailView_Lbl1stIsbnValue",  # FIXME/TODO: gibt es weitere?
                }
            )
            if x.get_text().strip()
        )
        # Beschreibung (1)
        description = tuple(
            x.get_text().strip()
            for x in self.find_all(
                attrs={
                    "id": f"{prefix}_MainView_UcDetailView_ucCatalogueDetailView_LblDescriptionValue",
                }
            )
            if x.get_text().strip()
        )
        if len(description) != 1:
            raise ValidationError(f"Es wurde eine Beschreibung erwartet (habe {len(description)=}).")
        self._attributes["description"] = description[0]
        # Treffernummer ermitteln
        match_number = [
            x.get_text().strip()
            for x in self.find_all(
                attrs={
                    "id": f"{prefix}_MainView_UcDetailView_LblDetailNavigator",
                }
            )
        ]
        if match_number:
            assert len(match_number) == 1, f"Es darf nur einen Treffer in der Detailanzeige geben ({len(match_number)=})."  # nicht fatal, daher nur assert
            match_number = match_number[0]
            if m := re.match(r"^(\d+?)\s+?von\s+?(\d+)$", match_number):
                match_number = int(m.group(1), 10)
                match_total = int(m.group(2), 10)
                match_index = match_number - 1
                self._attributes["match_entry"] = match_number
                self._attributes["match_index"] = match_index
                self._attributes["match_total"] = match_total
        # Tabelle mit Exemplaren in der jeweiligen Bibliothek
        copies_table = self.find_all("table", {"id": f"{prefix}_MainView_UcDetailView_ucCatalogueCopyView_grdViewMediumCopies"})
        if len(copies_table) != 1:
            raise ValidationError(f"Es kann nur eine Tabelle mit Exemplaren geben. Habe {len(copies_table)=}, {match_index=}.")
        if copies_table and len(copies_table) == 1:
            copies_table = copies_table[0]
            # Anmerkung: Status ist hier bspw. "In Einarbeitung" für neue Bücherlieferungen seitens der SBA
            copy_cols = tuple([x.get("abbr", None) or x.get_text() for x in copies_table.find_all("th", attrs={"scope": "col"})])
            if copy_cols not in self.valid_copy_cols:
                raise ValidationError(
                    f"Die Spalten stimmen nicht mit unseren Annahmen überein. Zeit das Skript anzupassen ({title=}, {match_index=}, {set(copy_cols)=!r})."
                )
            for elem in soup.select(f"table#{prefix}_MainView_UcDetailView_ucCatalogueCopyView_grdViewMediumCopies tr:has(td) td span.oclc-module-label"):
                elem.decompose()
            copies_rows = soup.select(f"table#{prefix}_MainView_UcDetailView_ucCatalogueCopyView_grdViewMediumCopies tr:has(td)")
            copies = []
            for row in copies_rows:
                col_contents = [x.get_text().replace("\n", " ").strip() for x in row.select("tr td")]
                if len(col_contents) != len(copy_cols):
                    raise ValidationError(
                        f"Es wurde erwartet daß die Anzahl Spalten im Tabellenkopf mit der Anzahl Spalten in den Zeilen übereinstimmt ({len(copies_cells)=} != {len(copy_cols)=})."
                    )
                copies.append(dict(zip(copy_cols, col_contents)))
            self._attributes["copies"] = copies
        # Validiere alle bisher belegten Attribute
        for name, validator in self._known_attributes.items():
            assert callable(validator), f"Brauche einen aufrufbaren Validator, habe {validator!r}."
            if name not in self._attributes:
                raise ValidationError(f"Nach dem Parsen hätten alle Attribute belegt sein sollen, '{name}' ist es nicht; {self._attributes=!r}.")
            if not validator(self._attributes[name]):
                raise ValidationError(f"Die Validierung für das Attribut '{name}' schlug fehl: {self._attributes[name]=!r}")
        self.soup = None
        delattr(self, "soup")

    def find_all(self, xmltype: Optional[Union[str, List[str]]] = None, attrs: dict = {}, soup=None):
        """\
        Sucht innerhalb der hübschen Suppe Elemente.
        """
        soup = soup or self.soup
        return soup.find_all(xmltype, attrs=attrs) if xmltype is not None else self.soup.find_all(attrs=attrs)

    def find_singleton(self, xmltype: Optional[Union[str, List[str]]], attrs: dict, soup=None):
        """\
        Sucht innerhalb der hübschen Suppe Elemente von denen es jeweils nur exakt eines geben darf.
        """
        elems = self.find_all(xmltype, attrs, soup)
        assert len(elems) == 1, f"Es wurde nur ein Element zurückerwartet (habe {len(elems)=}, {xmltype!r}, {attrs=})"
        return elems[0] if len(elems) == 1 else None

    def find_singleton_by_prefixed_id(self, id_suffix: str, soup=None):
        """\
        Sucht innerhalb der hübschen Suppe ein Element basierend auf seiner ID, ohne Tag usw.
        """
        return self.find_singleton(None, attrs={"id": f"{self.prefix}{id_suffix}"}, soup=soup)

    @cache
    def to_json_ready_dict(self):
        json_ready_dict = {}
        for key in self._known_attributes.keys():
            if not hasattr(self, key):
                raise ValidationError(f"Erwartetes Attribut '{key}' existiert nicht.")
            json_ready_dict[key] = getattr(self, key)
        return json_ready_dict


def main(**kwargs):
    """\
    Die Hauptfunktion
    """
    global log, cache
    log = setup_logging(kwargs.get("verbose", 0))
    cache = kwargs.get("cache", None)
    outfile = kwargs.get("outfile", Path(__file__).resolve().parent / "output.json")
    url = kwargs.get("url", None)
    assert url is not None, f"Die Einstiegs-URL kann nicht 'nichts' (None) sein."
    search = SBASearch(url, cache)
    book_details = []
    for idx, detail_url in search.items():
        book = SBABookDetails(search.get_details_soup(idx, detail_url))
        book_details.append(book.to_json_ready_dict())
    with open(outfile, "w") as json_file:
        json.dump(book_details, json_file, allow_nan=False, ensure_ascii=False, sort_keys=True, indent=4)


if __name__ == "__main__":
    args = parse_args()
    try:
        sys.exit(main(**vars(args)))
    except SBALogicError:
        print("Es wurde ein Logikproblem festgestellt, welches vermutlich eine Skriptanpassung benötigt!", file=sys.stderr)
        raise  # re-raise
    except KeyboardInterrupt:
        print("\nSIGINT", file=sys.stderr)
    except SystemExit:
        pass
    except ImportError:
        raise  # re-raise
    except RuntimeError:
        raise  # re-raise
    except Exception:
        print(__doc__)
        raise  # re-raise

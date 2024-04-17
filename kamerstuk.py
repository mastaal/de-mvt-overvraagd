"""
    kamerstuk.py

    Copyright (c) 2024 Martijn Staal `<de-mvt-overvraagd [a t ] martijn-staal.nl>`

    This file is available under the European Union Public License, v1.2 or later (EUPL-1.2).

    SPDX-License-Identifier: EUPL-1.2
"""

import json
import enum
import re
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element

import requests

re_whitespace = re.compile(r"\s+")
__KAMERSTUK_INFORMATION_CACHE_FILE_NAME = "kamerstuk_information.json"
__kamerstuk_information_cache: dict = {}


class KamerstukType(enum.Enum):
    """Specialized enum for kamerstuk types"""
    KONINKLIJKE_BOODSCHAP = "Koninklijke boodschap"
    GELEIDENDE_BRIEF = "Geleidende brief"
    WETSVOORSTEL = "Voorstel van wet"
    MEMORIE_VAN_TOELICHTING = "Memorie van toelichting"
    ADVIES_RVS = "Advies Raad van State"
    VOORLICHTING_RVS = "Voorlichting van de Afdeling advisering van de Raad van State"
    VERSLAG = "Verslag"
    NOTA_NA_VERSLAG = "Nota naar aanleiding van het verslag"
    NOTA_VAN_WIJZIGING = "Nota van wijziging"
    MEMORIE_VAN_ANTWOORD = "Memorie van antwoord"
    AMENDEMENT = "Amendement"
    MOTIE = "Motie"
    BRIEF = "Brief"
    JAARVERSLAG = "Jaarverslag"
    ONBEKEND = "Onbekend"


XML_NAMESPACES = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dcterms": "http://purl.org/dc/terms/",
    "psi": "http://psi.rechtspraak.nl/",
    "rs": "http://www.rechtspraak.nl/schema/rechtspraak-1.0",
    "ecli": "https://e-justice.europa.eu/ecli",
    "overheidwetgeving": "http://standaarden.overheid.nl/wetgeving/",
    "sru": "http://docs.oasis-open.org/ns/search-ws/sruResponse",
    "gzd": "http://standaarden.overheid.nl/sru",
    "c": "http://standaarden.overheid.nl/collectie/"
}


def __load_kamerstuk_information_cache() -> None:
    with open(__KAMERSTUK_INFORMATION_CACHE_FILE_NAME, "rt", encoding="utf-8") as cachejsonfile:
        try:
            __kamerstuk_information_cache = json.load(cachejsonfile)
        except json.decoder.JSONDecodeError:
            print("FATAL ERROR LOADING KAMERSTUK CACHE! Using empty cache instead.")
            __kamerstuk_information_cache = {}


def __save_kamerstuk_information_cache() -> None:
    with open(__KAMERSTUK_INFORMATION_CACHE_FILE_NAME, "wt", encoding="utf-8") as cachejsonfile:
        json.dump(__kamerstuk_information_cache, cachejsonfile)


def get_kamerstuktype_from_title(title: str, record: ET.Element, is_tail=False) -> KamerstukType:
    """Guess the kamerstuk document type from the title"""

    title = title.lower()
    title = title.replace('0', 'o')

    title_split = title.split('; ')
    try:
        title_tail = title_split[1]
    except IndexError:
        title_tail = ""

    try:
        opgegeven_kamerstuktype = record.find(".//overheidwetgeving:subrubriek[@scheme='OVERHEIDop.KamerstukTypen']", XML_NAMESPACES).text
    except AttributeError:
        opgegeven_kamerstuktype = ""

    if (opgegeven_kamerstuktype == "Brief" or
            title.startswith("brief")):
        return KamerstukType.BRIEF

    if opgegeven_kamerstuktype == "Amendement":
        return KamerstukType.AMENDEMENT

    if opgegeven_kamerstuktype == "Motie":
        return KamerstukType.MOTIE

    if opgegeven_kamerstuktype == "Voorstel van wet":
        return KamerstukType.WETSVOORSTEL

    if (opgegeven_kamerstuktype == "Koninklijke boodschap" or
            title.startswith("koninklijke boodschap")):
        return KamerstukType.KONINKLIJKE_BOODSCHAP

    if opgegeven_kamerstuktype == "Memorie van toelichting":
        return KamerstukType.MEMORIE_VAN_TOELICHTING

    if opgegeven_kamerstuktype == "Jaarverslag":
        return KamerstukType.JAARVERSLAG

    if opgegeven_kamerstuktype == "Verslag":
        return KamerstukType.VERSLAG

    if title.startswith("motie") or title.startswith("gewijzigde motie"):
        return KamerstukType.MOTIE

    if title.startswith("amendement") or title.startswith("gewijzigd amendement"):
        return KamerstukType.AMENDEMENT

    if (title.startswith("voorstel van wet") or
            title.startswith("gewijzigd voorstel van wet") or
            title.startswith("ontwerp van wet")):
        return KamerstukType.WETSVOORSTEL

    if title.endswith("voorstel van wet") or title.endswith("gewijzigd voorstel van wet"):
        return KamerstukType.WETSVOORSTEL

    if title.startswith("advies afdeling advisering raad van state") or title.startswith("advies raad van state"):
        return KamerstukType.ADVIES_RVS

    if title.startswith("voorlopig verslag") or title.startswith("verslag") or title.startswith("eindverslag") or title.startswith("nader voorlopig verslag"):
        return KamerstukType.VERSLAG

    if title.endswith("voorlopig verslag") or title.endswith("verslag") or title.endswith("eindverslag") or title.startswith("nader voorlopig verslag"):
        return KamerstukType.VERSLAG

    if title.startswith("nota naar aanleiding van het") or title.endswith("nota naar aanleiding van het"):
        return KamerstukType.NOTA_NA_VERSLAG

    if title.startswith("memorie van toelichting"):
        return KamerstukType.MEMORIE_VAN_TOELICHTING

    if title.endswith("memorie van toelichting"):
        return KamerstukType.MEMORIE_VAN_TOELICHTING

    if title.startswith("memorie van antwoord") or title.startswith("nadere memorie van antwoord"):
        return KamerstukType.MEMORIE_VAN_ANTWOORD

    if title.endswith("memorie van antwoord") or title.endswith("nadere memorie van antwoord"):
        return KamerstukType.MEMORIE_VAN_ANTWOORD

    if title.startswith("voorlichting van de afdeling advisering van de raad van state"):
        return KamerstukType.VOORLICHTING_RVS

    if title.lower().startswith("jaarverslag"):
        return KamerstukType.JAARVERSLAG

    if "nota van wijziging" in title.lower():
        # Beware, this lax check may result in errors
        return KamerstukType.NOTA_VAN_WIJZIGING

    print(f"Can't determine KamerstukType for {title}, trying to run on the tail")

    if not is_tail:
        tail_type = get_kamerstuktype_from_title(title_tail, record, is_tail=True)

        print(f"Found type {tail_type} using tail {title_tail}")
        return tail_type

    return KamerstukType.ONBEKEND


def koop_sru_api_request(query: str, start_record: int, maximum_records: int) -> Element:
    """Query the KOOP SRU API, return the complete response xml."""
    api_url = f"https://repository.overheid.nl/sru"

    resp = requests.get(
        api_url,
        params={
            "httpAccept": "application/xml",
            "startRecord": start_record,
            "maximumRecords": maximum_records,
            "query": query
        },
        timeout=25
    )

    if resp.status_code != 200:
        raise Exception(f"Non-200 status code while retrieving url with query {query}")

    xml: Element = ET.fromstring(resp.text)

    return xml


def koop_sru_api_request_all(query: str) -> list[Element]:
    """Query the KOOP SRU API. Returns all records for the query, even if this requires multiple requests.

    See https://data.overheid.nl/sites/default/files/dataset/d0cca537-44ea-48cf-9880-fa21e1a7058f/resources/Handleiding%2BSRU%2B2.0.pdf
    for more information about this API.
    """

    start_record = 0
    maximum_records = 100
    xml = koop_sru_api_request(query, start_record, maximum_records)
    records = xml.findall("sru:records/sru:record", XML_NAMESPACES)

    number_of_records = int(xml.find("sru:numberOfRecords", XML_NAMESPACES).text)

    while len(records) < number_of_records:
        # We need another request to get all the records!
        start_record = start_record + maximum_records
        xml = koop_sru_api_request(query, start_record, maximum_records)
        records += xml.findall("sru:records/sru:record", XML_NAMESPACES)

    return records


def get_kst_information(dossiernummer: str, ondernummer: str) -> dict:
    """Get information about a specific Kamerstuk using the KOOP SRU API

    Memoizes the results.
    """

    dossiernummer = re_whitespace.sub("", dossiernummer)
    ondernummer = re_whitespace.sub("", ondernummer)

    if dossiernummer in __kamerstuk_information_cache:
        if ondernummer in __kamerstuk_information_cache[dossiernummer]:
            return __kamerstuk_information_cache[dossiernummer][ondernummer]

    records = koop_sru_api_request_all(f"(w.dossiernummer={dossiernummer} AND w.ondernummer={ondernummer} AND dt.type=Kamerstuk)")

    # We assume this is the one we want
    record = records[0]

    product_area = record.find(".//c:product-area", XML_NAMESPACES).text

    if product_area == "sgd":
        # Old style!
        dossiernummer_record = record.find(".//overheidwetgeving:dossiernummer", XML_NAMESPACES).text
        ondernummer_record = record.find(".//overheidwetgeving:ondernummer", XML_NAMESPACES).text
        dossiertitel = record.find(".//dcterms:title", XML_NAMESPACES).text
        documenttitel = record.find(".//dcterms:description", XML_NAMESPACES).text
        vergaderjaar = record.find(".//overheidwetgeving:vergaderjaar", XML_NAMESPACES).text
        creator = record.find(".//dcterms:creator", XML_NAMESPACES).text

    elif product_area == "officielepublicaties":
        # New style
        dossiernummer_record = record.find(".//overheidwetgeving:dossiernummer", XML_NAMESPACES).text
        ondernummer_record = record.find(".//overheidwetgeving:ondernummer", XML_NAMESPACES).text
        dossiertitel = record.find(".//overheidwetgeving:dossiertitel", XML_NAMESPACES).text
        try:
            documenttitel = record.find(".//overheidwetgeving:documenttitel", XML_NAMESPACES).text
        except AttributeError:
            try:
                documenttitel = record.find(".//dcterms:title", XML_NAMESPACES).text
            except AttributeError:
                documenttitel = record.find(".//dcterms:description", XML_NAMESPACES).text
        vergaderjaar = record.find(".//overheidwetgeving:vergaderjaar", XML_NAMESPACES).text
        creator = record.find(".//dcterms:creator", XML_NAMESPACES).text

    if creator == "Tweede Kamer der Staten-Generaal":
        kamer = "II"
    elif creator == "Eerste Kamer der Staten-Generaal":
        kamer = "I"
    else:
        kamer = "??"

    # This check results in problems, for example when there is a Herdruk
    # if dossiernummer != dossiernummer_record or ondernummer != ondernummer_record:
    #     raise Exception("Record does not match request!")

    kst_info = {
        "dossiernummer": dossiernummer,
        "ondernummer": ondernummer,
        "vergaderjaar": str(vergaderjaar),
        "kamer": kamer,
        "kamerstuktype": get_kamerstuktype_from_title(documenttitel, record).value,
        "documenttitel": str(documenttitel),
        "dossiertitel": str(dossiertitel)
    }

    if dossiernummer not in __kamerstuk_information_cache:
        __kamerstuk_information_cache[dossiernummer] = {}

    __kamerstuk_information_cache[dossiernummer][ondernummer] = kst_info

    __save_kamerstuk_information_cache()

    return kst_info


__load_kamerstuk_information_cache()

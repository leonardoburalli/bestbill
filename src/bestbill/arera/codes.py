"""ARERA / SII code tables, transcribed from ``docs/arera-data.md``.

Each entry is marked *official* (documented in the SII spec or the AU
"Regole per il calcolo della spesa annua stimata") or *inferred* (derived
from the sample data, not yet checked against an authoritative source).
Keep this module in sync with ``docs/arera-data.md``; it holds no pricing
decisions (those live in :mod:`bestbill.arera.policy`).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "TipoMercato",
    "TipoCliente",
    "DomesticoResidente",
    "TipoOfferta",
    "TipologiaFasce",
    "FasciaComponente",
    "IdxPrezzoEnergia",
    "TipoDispacciamento",
    "Macroarea",
    "UnitaMisura",
    "ModalitaPagamento",
    "ScontoValidita",
    "ScontoCondizioneApplicazione",
    "PrezziScontoTipologia",
    "IvaSconto",
]


class TipoMercato(StrEnum):
    """official"""

    LIBERO = "01"


class TipoCliente(StrEnum):
    """official"""

    DOMESTICO = "01"
    NON_DOMESTICO = "02"


class DomesticoResidente(StrEnum):
    """official"""

    RESIDENTI = "01"
    NON_RESIDENTI = "02"
    ENTRAMBI = "03"


class TipoOfferta(StrEnum):
    """official"""

    FISSA = "01"
    VARIABILE = "02"


class TipologiaFasce(StrEnum):
    """official (01, 03, 91); 07 *inferred* (observed as "custom
    peak/off-peak"; not priced, see policy.SUPPORTED_TIPOLOGIA_FASCE).
    """

    MONO = "01"
    F1F2F3 = "03"
    F1F23 = "91"
    CUSTOM = "07"


class FasciaComponente(StrEnum):
    """official (01/02/03/91); 07/08 *inferred* (observed alongside
    TIPOLOGIA_FASCE=07, meaning unclear -- not priced).
    """

    F1_OR_MONO = "01"
    F2 = "02"
    F3 = "03"
    F23 = "91"
    CUSTOM_A = "07"
    CUSTOM_B = "08"


class IdxPrezzoEnergia(StrEnum):
    """official (12); 01/05 *official* per docs/arera-data.md; 08
    *inferred* (observed in the data, meaning not verified).
    """

    ALTRO_01 = "01"
    PE_MAGGIOR_TUTELA = "05"
    INFERRED_08 = "08"
    PUN_GME_MENSILE = "12"


class TipoDispacciamento(StrEnum):
    """official"""

    C_DISP = "01"
    PD_MT = "02"
    MSD = "03"
    CAPACITY_MARKET = "09"
    CAPACITY_MT = "10"
    RST = "11"
    RSTG = "12"
    DISPBT_FISSO_EUR_ANNO = "13"
    C_DISPD = "14"
    ALTRO_VALORE_DISP = "99"


class Macroarea(StrEnum):
    """official"""

    QUOTA_FISSA_COMMERCIALE = "01"
    QUOTA_VARIABILE_COMMERCIALE_ENERGIA = "02"
    QUOTA_VENDITA_ENERGIA_SPREAD = "04"
    ONE_OFF = "05"
    PREZZO_ENERGIA_RINNOVABILE = "06"


class UnitaMisura(StrEnum):
    """official"""

    EUR_ANNO = "01"
    EUR_KW_ANNO = "02"
    EUR_KWH = "03"
    EUR_SMC = "04"
    EUR_UNA_TANTUM = "05"
    PERCENTO = "06"


class ModalitaPagamento(StrEnum):
    """official (01-04); 99 *inferred*."""

    SDD = "01"
    BOLLETTINO = "02"
    CARTA = "03"
    BONIFICO = "04"
    ALTRO = "99"


class ScontoValidita(StrEnum):
    """official"""

    ALLINGRESSO = "01"
    ENTRO_12_MESI = "02"
    OLTRE_12_MESI = "03"


class ScontoCondizioneApplicazione(StrEnum):
    """official (00 unconditional); 01/02/03/99 *inferred* (meanings of
    the individual conditional codes not verified; all are treated as
    conditional by the policy module).
    """

    INCONDIZIONATO = "00"
    CONDIZIONE_01 = "01"
    CONDIZIONE_02 = "02"
    CONDIZIONE_03 = "03"
    CONDIZIONE_ALTRA = "99"


class PrezziScontoTipologia(StrEnum):
    """official"""

    FISSO = "01"
    VENDITA = "03"
    MAGGIOR_TUTELA = "04"


class IvaSconto(StrEnum):
    """official"""

    ANTE_IVA = "01"
    POST_IVA = "02"

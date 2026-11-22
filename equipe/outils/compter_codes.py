"""Outil : compter les patients par code dans une colonne clinique."""

import re

from smolagents import tool

from equipe.outils import acces


@tool
def compter_codes(colonne: str, puce: str) -> dict:
    """Compte les patients par code dans une colonne clinique codée, en séparant les cellules à plusieurs codes.

    Un patient dont la cellule vaut "1, 3" compte pour le code 1 et pour le code 3 : la somme des comptes
    peut donc dépasser le nombre de patients. Le sens de chaque code se lit avec codes_officiels.

    Args:
        colonne: le nom exact d'une colonne clinique, par exemple "Treatment_of_rhinitis".
        puce: "ALEX", "ISAC_V1" ou "ISAC_V2" pour ne garder qu'une puce ; "" pour toutes.
    """
    acces.verifier_colonne(colonne)
    cellules = acces.filtrer_puce(puce)[colonne]
    comptes = {}
    for cellule in cellules.dropna():
        # Un code apparaît au plus une fois par patient, même s'il est répété dans la cellule.
        for code in set(re.split(r"\s*,\s*", acces.en_texte(cellule).strip())):
            if code:
                comptes[code] = comptes.get(code, 0) + 1
    ordre = sorted(comptes, key=lambda code: (-comptes[code], code))
    return {
        "patients": len(cellules),
        "cases_vides": int(cellules.isna().sum()),
        "codes": {code: comptes[code] for code in ordre},
    }

"""Outil : compter les patients positifs à un dosage."""

from smolagents import tool

from equipe.outils import acces
from kit.donnees import COLONNE_PUCE


@tool
def positifs(colonne: str, seuil: float) -> dict:
    """Compte les patients positifs à un dosage : valeur supérieure ou égale au seuil, parmi les patients mesurés.

    Une case vide veut dire « non mesuré » (la puce de ce patient ne dose pas cet allergène) : elle ne compte
    ni parmi les positifs ni parmi les mesurés. Le détail est donné par puce.

    Args:
        colonne: le nom exact d'une colonne de dosage, par exemple "Phl_p_1".
        seuil: le seuil de positivité, par exemple 0.3.
    """
    acces.verifier_colonne(colonne)
    if colonne not in acces.colonnes_dosage():
        raise ValueError(f"{colonne} est une colonne clinique, pas un dosage : utilise compter_codes.")
    t = acces.tableau()
    mesures = t[colonne].notna()
    positif = t[colonne] >= seuil  # une case vide n'est jamais positive
    par_puce = {}
    for puce, groupe in t.groupby(COLONNE_PUCE):
        par_puce[puce] = {"mesures": int(mesures[groupe.index].sum()), "positifs": int(positif[groupe.index].sum())}
    total = int(mesures.sum())
    return {
        "colonne": colonne,
        "seuil": seuil,
        "mesures": total,
        "positifs": int(positif.sum()),
        "pourcentage": round(100 * int(positif.sum()) / total, 1) if total else None,
        "par_puce": par_puce,
    }

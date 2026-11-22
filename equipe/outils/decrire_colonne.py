"""Outil : décrire une colonne avant de s'en servir."""

import pandas as pd
from smolagents import tool

from equipe.outils import acces
from kit.donnees import COLONNE_PUCE, NB_CLINIQUES


@tool
def decrire_colonne(colonne: str) -> dict:
    """Décrit une colonne : son bloc, le nombre de valeurs renseignées (en tout et par puce), puis ses valeurs.

    Pour une colonne à peu de valeurs (un code clinique) : les valeurs les plus fréquentes.
    Pour une mesure : minimum, médiane, moyenne, maximum et nombre de zéros.
    Une case vide veut dire « non renseigné », ou, pour un dosage, « non mesuré par cette puce ».

    Args:
        colonne: le nom exact de la colonne, par exemple "Age" ou "Bet_v_1".
    """
    acces.verifier_colonne(colonne)
    t = acces.tableau()
    serie = t[colonne]
    description = {
        "colonne": colonne,
        "bloc": "clinique" if list(t.columns).index(colonne) < NB_CLINIQUES else "dosage",
        "lignes": len(serie),
        "renseignees": int(serie.notna().sum()),
        "renseignees_par_puce": {p: int(n) for p, n in serie.notna().groupby(t[COLONNE_PUCE]).sum().items()},
    }
    if pd.api.types.is_numeric_dtype(serie) and serie.nunique() > 12:
        description.update(
            minimum=float(serie.min()), mediane=float(serie.median()),
            moyenne=round(float(serie.mean()), 3), maximum=float(serie.max()),
            zeros=int((serie == 0).sum()),
        )
    else:
        frequentes = serie.value_counts().head(12)
        description["valeurs_frequentes"] = {acces.en_texte(v): int(n) for v, n in frequentes.items()}
    return description

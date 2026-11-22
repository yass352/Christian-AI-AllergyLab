"""Outil : regrouper les colonnes de dosage par famille d'allergènes."""

from smolagents import tool

from equipe.outils import acces
from equipe.outils.source_allergene import ALLERGENES, prefixe_de


@tool
def colonnes_par_famille(famille: str) -> dict:
    """Donne les colonnes de dosage d'une famille d'allergènes (« acarien », « pollen d'arbre », « aliment végétal »…).

    Avec famille "", donne la liste des familles et le nombre de colonnes de chacune.
    Une famille contient le mot cherché : "pollen" rassemble les pollens d'arbre, de graminée et d'herbacée.

    Args:
        famille: un mot du nom de la famille, ou "" pour la liste des familles.
    """
    table = acces.reference(ALLERGENES)
    familles = dict(zip(table["prefixe"], table["famille"]))
    groupes = {}
    for colonne in acces.colonnes_dosage():
        prefixe = prefixe_de(colonne, familles)
        groupes.setdefault(familles[prefixe] if prefixe else "inconnue", []).append(colonne)
    if not famille.strip():
        return {nom: len(colonnes) for nom, colonnes in sorted(groupes.items())}
    mot = famille.strip().lower()
    trouvees = {nom: colonnes for nom, colonnes in sorted(groupes.items()) if mot in nom.lower()}
    if not trouvees:
        raise ValueError(f"Aucune famille ne contient {famille!r}. Familles : {', '.join(sorted(groupes))}.")
    return trouvees

from smolagents import tool

from kit.donnees import charger, colonnes, lecture


@tool
def rapport_qualite() -> str:
    """Produit un rapport global de qualité des données allergologiques."""
    tableau = charger()
    dictionnaire = colonnes()

    lignes = len(tableau)
    colonnes_reelles = set(tableau.columns)
    colonnes_attendues = set(dictionnaire["colonne"])

    absentes = sorted(colonnes_attendues - colonnes_reelles)
    supplementaires = sorted(colonnes_reelles - colonnes_attendues)

    problemes_types = []
    for _, definition in dictionnaire.iterrows():
        nom = definition["colonne"]
        if nom not in tableau.columns:
            continue

        type_reel = lecture(tableau[nom])
        type_attendu = definition["lecture"]

        if type_reel != type_attendu:
            problemes_types.append(
                f"{nom} : attendu {type_attendu}, obtenu {type_reel}"
            )

    valeurs_manquantes = int(tableau.isna().sum().sum())
    cellules = lignes * len(tableau.columns)

    negatives_dosage = {}
    for _, definition in dictionnaire.iterrows():
        nom = definition["colonne"]
        if nom in tableau.columns and definition["bloc"] == "dosage":
            nombre = int((tableau[nom].dropna() < 0).sum())
            if nombre:
                negatives_dosage[nom] = nombre

    puces = tableau["Chip_Type"].value_counts(dropna=False)
    disponibilite = []

    colonnes_puces = [
        nom for nom in dictionnaire.columns
        if nom.startswith("puce_")
    ]

    for _, definition in dictionnaire.iterrows():
        nom = definition["colonne"]
        if nom not in tableau.columns:
            continue

        for colonne_puce in colonnes_puces:
            type_puce = colonne_puce.removeprefix("puce_")
            attendu = bool(definition[colonne_puce])

            if type_puce not in puces.index:
                continue

            valeurs = tableau.loc[
                tableau["Chip_Type"] == type_puce, nom
            ]
            renseigne = bool(valeurs.notna().any())

            if attendu and not renseigne:
                disponibilite.append(
                    f"{nom} : aucune valeur renseignée pour {type_puce}"
                )
            elif not attendu and renseigne:
                disponibilite.append(
                    f"{nom} : valeurs présentes alors que {type_puce} "
                    "est indiqué comme non disponible"
                )

    rapport = [
        "RAPPORT DE QUALITÉ DES DONNÉES",
        "",
        f"Nombre de lignes : {lignes}",
        f"Nombre de colonnes : {len(tableau.columns)}",
        f"Nombre de cellules : {cellules}",
        f"Valeurs manquantes : {valeurs_manquantes}",
        "",
        f"Colonnes absentes du fichier : {len(absentes)}",
        *[f"  - {nom}" for nom in absentes],
        f"Colonnes non répertoriées dans le dictionnaire : {len(supplementaires)}",
        *[f"  - {nom}" for nom in supplementaires],
        "",
        f"Anomalies de type : {len(problemes_types)}",
        *[f"  - {probleme}" for probleme in problemes_types],
        "",
        f"Colonnes de dosage avec valeurs négatives : {len(negatives_dosage)}",
        *[
            f"  - {nom} : {nombre} valeur(s)"
            for nom, nombre in negatives_dosage.items()
        ],
        "",
        f"Anomalies de disponibilité par puce : {len(disponibilite)}",
        *[f"  - {probleme}" for probleme in disponibilite],
        "",
        "Les valeurs négatives sont signalées pour examen. "
        "Leur signification n'est pas déduite automatiquement.",
    ]

    return "\n".join(rapport)

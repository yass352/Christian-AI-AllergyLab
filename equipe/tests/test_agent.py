"""L'agent de l'équipe, branché sur un faux modèle : ses outils, le tableau, et le contrôle du contrat."""

from pathlib import Path

import pandas as pd

from equipe import agent
from equipe.outils import acces
from kit.reponse import valider

# Ce que le faux modèle « écrit » : du code, entre les balises que smolagents attend.
APPEL_D_OUTIL = """<code>
liste = classer_allergenes(seuil=0.3, puce="", critere="nombre", nombre=1)
final_answer({"statut": "reponse", "valeur": liste[0]["colonne"], "justification": f"Classement sur {len(tableau)} lignes."})
</code>"""

HORS_CONTRAT = """<code>
final_answer({"statut": "reponse", "valeur": 12, "justification": "Une. Deux. Trois. Quatre."})
</code>"""

DANS_LE_CONTRAT = """<code>
final_answer({"statut": "reponse", "valeur": len(tableau), "justification": "Le tableau inventé compte douze lignes."})
</code>"""


def test_l_agent_appelle_un_outil_et_lit_le_tableau(faux_modele):
    faux_modele(APPEL_D_OUTIL)
    reponse = valider(agent.repondre("Quel allergène compte le plus de positifs ?"))
    assert reponse == {"statut": "reponse", "valeur": "Act_d_1", "justification": "Classement sur 12 lignes."}


def test_une_reponse_hors_contrat_est_refusee_puis_corrigee(faux_modele):
    faux = faux_modele(HORS_CONTRAT, DANS_LE_CONTRAT)
    reponse = valider(agent.repondre("Combien de lignes ?"))
    assert reponse["valeur"] == 12
    assert faux.reponses == []  # le modèle a été rappelé une fois de plus
    # Au second appel, le modèle a lu pourquoi sa première réponse était refusée.
    assert "trois au plus" in str(faux.recus[1])


def test_les_outils_sont_decrits_et_rendent_des_valeurs_simples():
    """Un outil rend un nombre, un texte, une liste ou un petit dictionnaire : jamais le tableau."""
    for outil in agent.OUTILS:
        assert outil.description and outil.inputs
        assert outil.output_type in ("string", "integer", "number", "boolean", "array", "object")


def test_les_deux_lignes_d_acces_aux_donnees_restent_visibles():
    """README : l'accès aux données tient en deux lignes signalées par un commentaire, faciles à retirer."""
    texte = Path(agent.__file__).read_text(encoding="utf-8")
    assert texte.count("# Accès aux données :") == 2
    assert 'additional_authorized_imports=["pandas"]' in texte
    assert 'additional_args={"tableau": charger(), **acces.complements()}' in texte


def test_l_agent_recoit_les_donnees_complementaires_et_calcule_dessus(faux_modele):
    """Chaque fichier de donnees_complementaires/ arrive chargé : une réponse peut s'appuyer sur lui seul."""
    faux_modele("""<code>
final_answer({"statut": "reponse", "valeur": len(risque_lyon), "justification": "Bulletins de Lyon."})
</code>""")
    reponse = valider(agent.repondre("Combien de lignes comptent les bulletins de risque de Lyon ?"))
    assert reponse["valeur"] == len(acces.complements()["risque_lyon"])


def test_les_donnees_complementaires_ont_leurs_colonnes():
    """La forme des tables que décrit equipe/consigne.md : leurs colonnes et leurs types."""
    tables = acces.complements()
    assert set(tables) == set(acces.COMPLEMENTAIRES)
    assert all(len(table) > 0 for table in tables.values())
    assert {"taxon", "mois", "moyenne_grains_m3", "allergenes_acc"} <= set(tables["pollens_mois"].columns)
    assert {"taxon", "annee", "indice_pollinique_median"} <= set(tables["pollens_annees"].columns)
    assert {"station", "zone", "taxon", "mois", "moyenne_grains_m3"} <= set(tables["pollens_capteurs"].columns)
    assert {"type", "designation", "quantite", "raep", "date_bulletin"} <= set(tables["risque_lyon"].columns)
    assert {"variable", "code", "libelle"} == set(tables["dictionnaire"].columns)
    lyon = tables["risque_lyon"]
    assert pd.api.types.is_numeric_dtype(lyon["quantite"])
    assert pd.api.types.is_datetime64_any_dtype(lyon["date_bulletin"])

"""Poser une question à l'agent de l'équipe : `uv run kit agent "…"`.

Le kit ne connaît de l'agent qu'une fonction : repondre(question), dans
equipe/agent.py. Il l'appelle, vérifie que la réponse respecte le contrat en
trois champs (kit/reponse.py), affiche la réponse, les jetons consommés et
leur coût estimé, puis écrit la trace (kit/traces.py), même en cas d'erreur.
"""

import importlib
import sys

from kit import modele, traces
from kit.cle import CleAbsente
from kit.donnees import RACINE
from kit.reponse import CHAMPS, ReponseIllisible, valider

# Les erreurs qui ont un message prévu : le kit dit ce qui ne va pas, puis quoi faire.
ERREURS_PREVUES = (modele.ErreurModele, CleAbsente, ReponseIllisible)


def charger_repondre(racine=RACINE):
    """La fonction repondre de equipe/agent.py."""
    # Le dossier du dépôt en tête du chemin d'import : agent.py peut importer equipe.outils.
    if str(racine) not in sys.path:
        sys.path.insert(0, str(racine))
    return importlib.import_module("equipe.agent").repondre


def erreur_prevue(erreur):
    """L'erreur prévue d'où vient erreur, ou None. smolagents enveloppe les erreurs du modèle dans les siennes."""
    for _ in range(10):
        if erreur is None or isinstance(erreur, ERREURS_PREVUES):
            return erreur
        erreur = erreur.__cause__ or erreur.__context__
    return None


def poser(question, racine=RACINE):
    """Pose la question, affiche le résultat, écrit la trace. Rend 0 si la réponse respecte le contrat."""
    modele.journal_neuf()
    sortie, trace = None, None
    try:
        with traces.appel(question, None, None, racine) as trace:
            try:
                sortie = charger_repondre(racine)(question)
                if modele.journal["erreur"]:  # une erreur finale que smolagents a avalée
                    raise modele.journal["erreur"]
                trace.noter(reponse=sortie)
                reponse = valider(sortie)
                trace.noter(reponse=reponse)
            except Exception as erreur:
                prevue = erreur_prevue(erreur)
                if prevue is None or prevue is erreur:
                    raise
                raise prevue from None
            finally:
                trace.noter(**{nom: modele.journal[nom] for nom in ("moteur", "modele", "etapes", "jetons", "cout_estime")})
    except ERREURS_PREVUES as erreur:
        afficher_erreur(erreur, sortie)
        code = 1
    else:
        afficher_reponse(reponse)
        code = 0
    finally:
        afficher_bilan(trace, racine)
    return code


def afficher_reponse(reponse):
    print("Réponse de l'agent")
    for nom in CHAMPS:
        print(f"  {nom:<14} {'(vide)' if reponse[nom] is None else reponse[nom]}")


def afficher_erreur(erreur, sortie):
    if isinstance(erreur, ReponseIllisible):
        print(f"Réponse illisible : {erreur}")
        print(f"Ce que l'agent a rendu : {modele.tronquer(repr(sortie))}")
        print(
            "Que faire : la réponse finale passe par final_answer, avec les trois champs "
            "statut, valeur, justification. Le format est écrit dans kit/reponse.py."
        )
        return
    print(erreur.texte[0].upper() + erreur.texte[1:])
    print(f"Que faire : {erreur.que_faire}")


def milliers(nombre):
    return f"{nombre:,}".replace(",", " ")


def afficher_bilan(trace, racine):
    """Jetons, coût estimé et chemin de la trace : affichés à chaque exécution, réussie ou non."""
    journal = modele.journal
    if journal["modele"]:
        jetons = journal["jetons"]
        print(
            f"Jetons : {milliers(jetons['entree'])} en entrée, {milliers(jetons['sortie'])} en sortie "
            f"({journal['modele']}). Coût estimé : {modele.en_dollars(journal['cout_estime'])}."
        )
    else:
        print("Jetons : aucun appel au modèle n'a abouti.")
    if trace is not None and trace.chemin is not None:
        print(f"Trace : {trace.chemin.relative_to(racine).as_posix()}")

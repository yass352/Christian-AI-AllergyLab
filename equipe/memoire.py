"""Pas un outil : la mémoire des réponses, lue dans les traces que le kit écrit déjà.

Une question déjà posée, mot pour mot, au même agent et au même modèle
reprend la réponse enregistrée dans sa trace, sans nouvel appel au modèle :
zéro jeton. « Le même agent », c'est la même empreinte d'état, celle que le
kit calcule sur agent.py, consigne.md, outils/ et questions/ : dès que l'un
d'eux change, les anciennes réponses ne sont plus reprises.

Les majuscules et les espaces en trop ne comptent pas ; un seul mot changé,
et la question est nouvelle. Les traces sont poussées avec le reste du
dépôt : une réponse obtenue sur une machine sert aussi aux autres.
"""

import json

from kit import modele, traces
from kit.donnees import RACINE
from kit.reponse import ReponseIllisible, valider


def normaliser(question):
    """La question telle que la trace l'a gardée (anonymisée), sans majuscules ni espaces en trop."""
    return " ".join(traces.anonymiser(question).split()).casefold()


def reponse_enregistree(question, racine=RACINE):
    """(réponse, chemin de la trace) pour une question déjà traitée par cet agent et ce modèle, ou None."""
    etat = traces.empreinte_etat(traces.lire_etat(racine / "equipe"))
    identifiant = modele.choisi()["identifiant"]
    cherchee = normaliser(question)
    # Les noms des traces suivent l'heure : en ordre inverse, la plus récente d'abord.
    for chemin in sorted((racine / "traces" / "appels").rglob("*.json"), reverse=True):
        try:
            trace = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(trace, dict) or not isinstance(trace.get("question"), str):
            continue
        # Seule une réponse que le modèle a réellement produite sert de source, jamais une réponse déjà reprise.
        if trace.get("etat") != etat or trace.get("modele") != identifiant or trace.get("erreur"):
            continue
        if normaliser(trace["question"]) != cherchee:
            continue
        try:
            return valider(trace.get("reponse")), chemin.relative_to(racine).as_posix()
        except ReponseIllisible:
            continue
    return None

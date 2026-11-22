"""Le contrat de réponse : trois champs, leur validation, et la consigne qui les demande.

Une réponse de l'agent a trois champs (SPEC § 5.3) :

    statut         "reponse" ou "abstention"
    valeur         un nombre ou un texte ; vide (None) en cas d'abstention
    justification  une à trois phrases

Le kit fixe la forme d'une réponse, et celle d'une abstention. Il ne dit
jamais quand s'abstenir : c'est le travail de l'équipe, dans sa consigne.
"""

import json
import math
import numbers
import re

CHAMPS = ("statut", "valeur", "justification")
STATUTS = ("reponse", "abstention")

# Ajouté à la consigne de l'équipe : la forme de la réponse, et rien d'autre.
FORMAT = """\
Format de la réponse finale, fixé par le kit : appelle final_answer avec un dictionnaire de trois clés, et de trois seulement.
- "statut" : "reponse", ou "abstention" pour dire que tu ne peux pas conclure.
- "valeur" : un nombre (int ou float, sans unité ni séparateur de milliers) ou un texte court ; None en cas d'abstention.
- "justification" : une à trois phrases.
Forme : final_answer({"statut": ..., "valeur": ..., "justification": ...})"""


class ReponseIllisible(ValueError):
    """Une sortie de l'agent qui ne respecte pas le contrat."""


def consigne(texte_equipe):
    """La consigne donnée au modèle : celle de l'équipe, puis le format de réponse."""
    return f"{texte_equipe.strip()}\n\n{FORMAT}"


def est_nombre(valeur):
    return isinstance(valeur, numbers.Real) and not isinstance(valeur, bool) and math.isfinite(valeur)


def est_vide(valeur):
    return valeur is None or (isinstance(valeur, str) and not valeur.strip())


def phrases(texte):
    """Le nombre de phrases d'un texte : une fin de phrase est . ! ? ou …, suivi d'un blanc ou de la fin."""
    return len(re.findall(r"[.!?…]+(?=\s|$)", texte.strip())) or 1


def valider(sortie):
    """Rend la réponse en trois champs si sortie respecte le contrat ; lève ReponseIllisible sinon."""
    reponse = sortie
    if isinstance(sortie, str):
        try:
            reponse = json.loads(sortie)
        except ValueError:
            raise ReponseIllisible("l'agent a rendu un texte, pas les trois champs du contrat.") from None
    if not isinstance(reponse, dict):
        raise ReponseIllisible(f"l'agent a rendu un objet {type(reponse).__name__}, pas un dictionnaire.")
    if sorted(map(str, reponse)) != sorted(CHAMPS):
        noms = ", ".join(map(str, reponse)) or "aucun"
        raise ReponseIllisible(f"les champs sont : {noms} ; le contrat demande statut, valeur, justification.")
    statut, valeur, justification = (reponse[nom] for nom in CHAMPS)
    if statut not in STATUTS:
        raise ReponseIllisible(f"le statut vaut {statut!r} ; il doit valoir \"reponse\" ou \"abstention\".")
    if statut == "abstention" and not est_vide(valeur):
        raise ReponseIllisible("une abstention a une valeur vide (None).")
    if statut == "reponse" and not (est_nombre(valeur) or (isinstance(valeur, str) and valeur.strip())):
        raise ReponseIllisible("la valeur d'une réponse est un nombre ou un texte non vide.")
    if not isinstance(justification, str) or not justification.strip():
        raise ReponseIllisible("la justification est un texte non vide.")
    if phrases(justification) > 3:
        raise ReponseIllisible(f"la justification compte {phrases(justification)} phrases ; trois au plus.")
    if est_nombre(valeur):
        valeur = int(valeur) if isinstance(valeur, numbers.Integral) else float(valeur)
    elif est_vide(valeur):
        valeur = None
    return {"statut": statut, "valeur": valeur, "justification": justification.strip()}

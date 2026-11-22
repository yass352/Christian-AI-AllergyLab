"""Un exemple de syntaxe d'outil, sans rapport avec les données. Il n'est branché sur aucun agent.

Un outil est une fonction Python ordinaire, décorée par @tool. smolagents lit
sa signature et sa docstring pour le décrire au modèle : les types des
paramètres, le type rendu et la section Args sont obligatoires. Un outil rend
une valeur simple (un nombre, un texte, une courte liste), jamais le tableau.

Pour brancher un outil, dans equipe/agent.py :
    from equipe.outils.exemple import compter_mots
puis tools=[compter_mots] dans l'appel à CodeAgent.
"""

from smolagents import tool


@tool
def compter_mots(texte: str) -> int:
    """Compte les mots d'un texte, séparés par des espaces.

    Args:
        texte: le texte dont on compte les mots.
    """
    return len(texte.split())

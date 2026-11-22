"""La boucle maison : le repli, si smolagents ou LiteLLM cassent (SPEC § 5.3).

Une boucle d'outils écrite à la main, sur l'appel sans framework que le
contrôle 2 de kit/tester-la-stack.py valide. Elle n'exécute aucun code écrit
par le modèle : elle ne sait qu'appeler les outils de l'équipe. C'est un mode
dégradé, avec le même contrat de réponse.

Pour l'activer, une ligne change dans equipe/agent.py :

    from smolagents import CodeAgent
devient
    from kit.boucle_maison import BoucleMaison as CodeAgent

Les outils restent les mêmes. La boucle accepte les autres paramètres du
CodeAgent pour que rien d'autre ne change, mais le tableau et l'import de
pandas ne lui servent à rien : sans exécution de code, elle les ignore.
"""

from smolagents.models import get_tool_json_schema

from kit import modele

MAX_JETONS = 4096  # longueur maximale d'une réponse du modèle, à chaque étape

# La réponse finale est un outil de plus, dont les trois paramètres sont les trois champs du contrat.
REPONSE_FINALE = {
    "name": "final_answer",
    "description": "Donne la réponse finale, en trois champs.",
    "input_schema": {
        "type": "object",
        "properties": {
            "statut": {"type": "string", "enum": ["reponse", "abstention"]},
            "valeur": {"type": ["number", "string", "null"]},
            "justification": {"type": "string"},
        },
        "required": ["statut", "valeur", "justification"],
    },
}


def decrire(outil):
    """Un outil de smolagents, décrit dans la forme qu'attend l'API d'Anthropic."""
    fonction = get_tool_json_schema(outil)["function"]
    return {"name": fonction["name"], "description": fonction["description"], "input_schema": fonction["parameters"]}


class BoucleMaison:
    def __init__(self, tools, instructions="", max_steps=8, **ignores):
        self.outils = {outil.name: outil for outil in tools}
        self.consigne = instructions or ""
        self.etapes_max = max_steps

    def run(self, question, additional_args=None):
        messages = [{"role": "user", "content": question}]
        descriptions = [decrire(outil) for outil in self.outils.values()] + [REPONSE_FINALE]
        for _ in range(self.etapes_max):
            reponse = modele.messages(max_tokens=MAX_JETONS, system=self.consigne, tools=descriptions, messages=messages)
            messages.append({"role": "assistant", "content": reponse.content})
            appels = [bloc for bloc in reponse.content if bloc.type == "tool_use"]
            if not appels:  # le modèle a répondu en texte : le kit tentera de le lire
                return "".join(bloc.text for bloc in reponse.content if bloc.type == "text")
            resultats = []
            for appel in appels:
                if appel.name == "final_answer":
                    modele.ajouter_etape(f"final_answer({appel.input})", None)
                    return appel.input
                resultat, erreur = self.executer(appel.name, appel.input)
                modele.ajouter_etape(f"{appel.name}({appel.input})", resultat)
                resultats.append({
                    "type": "tool_result", "tool_use_id": appel.id,
                    "content": modele.tronquer(resultat), "is_error": erreur,
                })
            messages.append({"role": "user", "content": resultats})
        return f"Plafond de {self.etapes_max} étapes atteint sans réponse finale."

    def executer(self, nom, arguments):
        """Appelle un outil de l'équipe. Rend (résultat en texte, vrai si erreur)."""
        if nom not in self.outils:
            return f"Outil inconnu : {nom}. Outils disponibles : {', '.join(self.outils) or 'aucun'}.", True
        try:
            return str(self.outils[nom](**arguments)), False
        except Exception as erreur:  # l'erreur d'un outil est rendue au modèle, qui peut corriger
            return f"Erreur : {type(erreur).__name__} : {erreur}", True

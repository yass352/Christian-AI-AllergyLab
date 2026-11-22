#!/usr/bin/env python3
"""
AllergyLab - La stack repond-elle ?

A lancer AVANT la semaine, depuis le dossier du kit :

    export ANTHROPIC_API_KEY=CLE_API_ICI
    python3 tester-la-stack.py

Trois controles, du plus simple au plus complet :
  1. appel direct a l'API, sans framework
  2. appel d'outil direct, sans framework
  3. meme chose a travers smolagents

Le but est de savoir lequel casse. Si 1 et 2 passent et que 3 echoue,
le probleme vient du framework et de ce qu'il ajoute a la requete,
pas de la cle ni du modele.
"""

import os
import sys

MODELES = ["claude-haiku-5-5", "claude-sonnet-5-5"]

VERT, ROUGE, JAUNE, GRIS, FIN = "\033[92m", "\033[91m", "\033[93m", "\033[90m", "\033[0m"


def ok(m):    print(f"  {VERT}OK{FIN}      {m}")
def echec(m): print(f"  {ROUGE}ECHEC{FIN}   {m}")
def info(m):  print(f"  {GRIS}{m}{FIN}")
def alerte(m):print(f"  {JAUNE}ATTENTION{FIN} {m}")


def expliquer(e):
    """Rend lisible une erreur d'API."""
    txt = str(e)
    if "400" in txt or "invalid_request" in txt:
        alerte("erreur 400 : la requete contient un parametre que le modele refuse.")
        for p in ("temperature", "top_p", "top_k", "tool_choice", "budget_tokens"):
            if p in txt:
                info(f"parametre en cause, nomme par l'API : {p}")
    elif "401" in txt or "authentication" in txt.lower():
        alerte("erreur 401 : la cle est absente, expiree ou mal copiee.")
    elif "429" in txt:
        alerte("erreur 429 : debit depasse. Reessaie dans une minute.")
    elif "credit" in txt.lower() or "balance" in txt.lower():
        alerte("solde insuffisant sur le workspace.")
    info(txt[:300])


def test_appel_simple(client, modele):
    r = client.messages.create(
        model=modele,
        max_tokens=64,
        messages=[{"role": "user", "content": "Reponds exactement : pret"}],
    )
    texte = "".join(b.text for b in r.content if b.type == "text").strip()
    return texte, r.usage


OUTIL = {
    "name": "compter_lignes",
    "description": "Renvoie le nombre de lignes d'un fichier de donnees.",
    "input_schema": {
        "type": "object",
        "properties": {"fichier": {"type": "string", "description": "nom du fichier"}},
        "required": ["fichier"],
    },
}


def test_appel_outil(client, modele):
    r = client.messages.create(
        model=modele,
        max_tokens=256,
        tools=[OUTIL],
        messages=[{"role": "user", "content": "Combien de lignes dans fichier-fictif.csv ? Utilise l'outil."}],
    )
    return [b for b in r.content if b.type == "tool_use"]


def main():
    cle = os.environ.get("ANTHROPIC_API_KEY")
    print(f"\n{'=' * 64}\n  VERIFICATION DE LA STACK\n{'=' * 64}\n")

    if not cle:
        echec("ANTHROPIC_API_KEY absente de l'environnement.")
        info("export ANTHROPIC_API_KEY=CLE_API_ICI   puis relance.")
        return 1
    ok("cle presente")

    try:
        import anthropic
    except ImportError:
        echec("paquet 'anthropic' absent.  ->  pip install anthropic")
        return 1
    ok(f"anthropic {anthropic.__version__}")

    client = anthropic.Anthropic(api_key=cle)
    vivants = []

    print("\n1. Appel direct\n" + "-" * 64)
    for m in MODELES:
        try:
            texte, usage = test_appel_simple(client, m)
            ok(f"{m} -> {texte!r}  ({usage.input_tokens} entree / {usage.output_tokens} sortie)")
            vivants.append(m)
        except Exception as e:
            echec(m)
            expliquer(e)

    if not vivants:
        print("\nAucun modele ne repond. Inutile d'aller plus loin.\n")
        return 1

    print("\n2. Appel d'outil, sans framework\n" + "-" * 64)
    for m in vivants:
        try:
            appels = test_appel_outil(client, m)
            if appels:
                ok(f"{m} appelle bien l'outil : {appels[0].name}({appels[0].input})")
            else:
                alerte(f"{m} n'a pas appele l'outil. Le prompt de l'agent devra etre plus directif.")
        except Exception as e:
            echec(m)
            expliquer(e)

    print("\n3. A travers smolagents\n" + "-" * 64)
    try:
        from smolagents import ToolCallingAgent, LiteLLMModel, tool
    except ImportError:
        alerte("smolagents absent.  ->  pip install 'smolagents[litellm]'")
        info("Les controles 1 et 2 suffisent a valider la cle et le modele.")
        return 0

    @tool
    def compter_lignes(fichier: str) -> int:
        """Renvoie le nombre de lignes d'un fichier de donnees.

        Args:
            fichier: nom du fichier a mesurer.
        """
        return 1

    for m in vivants:
        try:
            agent = ToolCallingAgent(tools=[compter_lignes], model=LiteLLMModel(model_id=f"anthropic/{m}"))
            reponse = agent.run("Combien de lignes dans fichier-fictif.csv ?")
            ok(f"{m} -> {str(reponse)[:80]}")
        except Exception as e:
            echec(f"{m} via smolagents")
            expliquer(e)
            info("Si les controles 1 et 2 passaient, c'est smolagents ou LiteLLM")
            info("qui ajoute un parametre de trop. Repli : la boucle d'outils maison.")

    print(f"\n{'=' * 64}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

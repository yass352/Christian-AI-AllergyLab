"""Notre banc d'essai : fait passer un lot de questions à l'agent et calcule les trois mesures du défi.

Usage, depuis le dossier du dépôt :
    uv run python equipe/analyse/evaluer.py                      # lot 01, modèle du développement
    uv run python equipe/analyse/evaluer.py equipe/questions/lot_01.toml --seulement q08 a04

Chaque question passe par le même chemin que `uv run kit agent` (kit.question.poser) :
la trace de chaque appel s'écrit dans traces/appels/ comme d'habitude. Ce script
coûte des jetons : environ 31 questions × 2 à 4 étapes, sur Haiku.

Verdicts, comme le harnais d'évaluation annoncé (SPEC § 5.4) : juste, faux,
abstention fondée, abstention à tort, réponse inventée, illisible.
"""

import contextlib
import io
import json
import re
import sys
import tomllib
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from kit.question import poser  # noqa: E402


def verdict(question, reponse):
    if reponse is None:
        return "illisible"
    abstient = reponse["statut"] == "abstention"
    if question["type"] == "sans-reponse":
        return "abstention fondée" if abstient else "réponse inventée"
    if abstient:
        return "abstention à tort"
    valeur, attendu = reponse["valeur"], question["attendu"]
    if question["type"] == "nombre":
        try:
            return "juste" if abs(float(valeur) - float(attendu)) <= question.get("tolerance", 0) + 1e-9 else "faux"
        except (TypeError, ValueError):
            return "faux"
    return "juste" if str(valeur).strip().lower() == str(attendu).strip().lower() else "faux"


def lancer(question):
    """Pose la question comme `kit agent`, puis relit la trace écrite par le kit."""
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        poser(question["texte"])
    trouve = re.search(r"Trace : (\S+)", sortie.getvalue())
    if not trouve:
        return {"reponse": None, "jetons": {"entree": 0, "sortie": 0}, "cout_estime": 0, "duree_s": 0}
    trace = json.loads((RACINE / trouve.group(1)).read_text(encoding="utf-8"))
    if not isinstance(trace.get("reponse"), dict) or "statut" not in trace["reponse"] or trace.get("erreur"):
        trace["reponse"] = None
    return trace


def main(arguments):
    chemin = Path(arguments[0]) if arguments and not arguments[0].startswith("--") else RACINE / "equipe/questions/lot_01.toml"
    seulement = arguments[arguments.index("--seulement") + 1:] if "--seulement" in arguments else None
    questions = tomllib.loads(chemin.read_text(encoding="utf-8"))["question"]
    if seulement:
        questions = [q for q in questions if q["id"] in seulement]
    comptes, jetons, cout, duree = {}, 0, 0.0, 0.0
    for question in questions:
        trace = lancer(question)
        resultat = verdict(question, trace["reponse"])
        comptes[resultat] = comptes.get(resultat, 0) + 1
        jetons += trace["jetons"]["entree"] + trace["jetons"]["sortie"]
        cout += trace["cout_estime"] or 0
        duree += trace["duree_s"] or 0
        valeur = trace["reponse"]["valeur"] if trace["reponse"] else "—"
        print(f"{question['id']:<4} {resultat:<18} valeur={valeur!s:<10} attendu={question.get('attendu', '—')}")
    avec = [q for q in questions if q["type"] != "sans-reponse"]
    sans = [q for q in questions if q["type"] == "sans-reponse"]
    n = len(questions) or 1
    print()
    if avec:
        print(f"Justesse   : {comptes.get('juste', 0)}/{len(avec)} = {100 * comptes.get('juste', 0) / len(avec):.1f} %")
    if sans:
        print(f"Abstention : {comptes.get('abstention fondée', 0)}/{len(sans)} = {100 * comptes.get('abstention fondée', 0) / len(sans):.1f} %")
    print(f"Frugalité  : {jetons / n:.0f} jetons, {cout / n:.5f} $ et {duree / n:.1f} s par question en moyenne")
    print("Verdicts   :", ", ".join(f"{k} {v}" for k, v in sorted(comptes.items())))


if __name__ == "__main__":
    main(sys.argv[1:])

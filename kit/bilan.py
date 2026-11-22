"""Le bilan des traces du dépôt : `uv run kit bilan`.

Il lit traces/, n'appelle pas le modèle et n'écrit rien. Trois parties :
- par jour, les appels à l'agent et les questions évaluées, leurs jetons et
  leur coût estimé ;
- les évaluations, avec leurs deux scores, côte à côte ;
- les traces que le dépôt de l'équipe n'a pas encore.

Le tableau se recalcule à chaque fois, il ne se stocke pas (SPEC § 7.3). Les
coûts sont des estimations, aux tarifs de kit/reglages.toml : le relevé exact
est dans la console d'Anthropic.
"""

import json
from collections import defaultdict

from kit import donnees, pousser
from kit.donnees import RACINE
from kit.evaluer import en_dollars, milliers, relatif, score
from kit.reponse import est_nombre


def lire(dossier):
    """Les traces JSON d'un dossier de traces/, et le nombre de fichiers qui ne se lisent pas."""
    lues, illisibles = [], 0
    for chemin in sorted(dossier.rglob("*.json")) if dossier.is_dir() else []:
        if any(partie.startswith(".") for partie in chemin.relative_to(dossier).parts):
            continue
        try:
            trace = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            trace = None
        if isinstance(trace, dict) and isinstance(trace.get("horodatage"), str):
            lues.append(trace)
        else:
            illisibles += 1
    return lues, illisibles


def nombre(valeur):
    return valeur if est_nombre(valeur) else 0


def ajouter(jour, trace):
    """Ajoute au décompte d'un jour les jetons et le coût d'un appel, ou d'une question évaluée."""
    jetons = trace.get("jetons") if isinstance(trace.get("jetons"), dict) else {}
    jour["lus"] += nombre(jetons.get("entree"))
    jour["ecrits"] += nombre(jetons.get("sortie"))
    jour["cout"] += nombre(trace.get("cout_estime"))


def par_jour(appels, evaluations):
    jours = defaultdict(lambda: {"appels": 0, "questions": 0, "lus": 0, "ecrits": 0, "cout": 0.0})
    for appel in appels:
        jours[appel["horodatage"][:10]]["appels"] += 1
        ajouter(jours[appel["horodatage"][:10]], appel)
    for evaluation in evaluations:
        for question in evaluation.get("questions") or []:
            if isinstance(question, dict):
                jours[evaluation["horodatage"][:10]]["questions"] += 1
                ajouter(jours[evaluation["horodatage"][:10]], question)
    return dict(sorted(jours.items()))


def afficher_jour(jour, compte):
    print(
        f"  {jour:<12}{compte['appels']:>8}{compte['questions']:>11}{milliers(compte['lus']):>13}"
        f"{milliers(compte['ecrits']):>15}{en_dollars(compte['cout']):>14}"
    )


def afficher_jours(jours):
    print("Par jour (appels : uv run kit agent ; questions : celles des évaluations)")
    print(f"  {'jour':<12}{'appels':>8}{'questions':>11}{'jetons lus':>13}{'jetons écrits':>15}{'coût estimé':>14}")
    total = {"appels": 0, "questions": 0, "lus": 0, "ecrits": 0, "cout": 0.0}
    for jour, compte in jours.items():
        afficher_jour(jour, compte)
        for cle in total:
            total[cle] += compte[cle]
    afficher_jour("total", total)


def afficher_evaluations(evaluations, racine):
    print("Évaluations")
    table_inventee = relatif(donnees.EXEMPLE, racine)
    for evaluation in sorted(evaluations, key=lambda e: e["horodatage"]):
        batterie = evaluation.get("batterie") if isinstance(evaluation.get("batterie"), dict) else {}
        marques = [str(batterie.get("chemin")), str(evaluation.get("modele"))]
        if evaluation.get("table") == table_inventee:
            marques.append("table inventée")
        if evaluation.get("officielle"):
            marques.append("passe officielle")
        if evaluation.get("erreur"):
            marques.append("arrêtée avant la fin")
        quand = evaluation["horodatage"].replace("T", " ")[:16]
        print(f"  {quand} UTC  {', '.join(marques)}")
        frugal = evaluation.get("frugalite") if isinstance(evaluation.get("frugalite"), dict) else {}
        total = frugal.get("total") if isinstance(frugal.get("total"), dict) else {}
        questions = len(evaluation.get("questions") or [])
        print(
            f"  {'':<20}  justesse {score(evaluation.get('justesse'), 'justes')} | "
            f"abstention {score(evaluation.get('abstention'), 'fondees')} | "
            f"{questions} question{'s' if questions > 1 else ''}, {en_dollars(nombre(total.get('cout_estime')))}"
        )


def afficher_non_poussees(racine):
    non_poussees = pousser.traces_non_poussees(racine)
    if non_poussees is None:
        print("Traces non poussées : impossible à dire ici, sans dépôt git ou sans dépôt d'équipe auquel comparer.")
    elif pousser.decompte(non_poussees):
        print(f"Traces non poussées : {pousser.decompte(non_poussees)} ; pour les envoyer, uv run kit pousser")
    else:
        print("Traces non poussées : aucune, d'après le dernier échange avec le dépôt de l'équipe.")


def bilan(racine=RACINE):
    """Affiche le bilan des traces de racine. Rend 0."""
    appels, illisibles_a = lire(racine / "traces" / "appels")
    evaluations, illisibles_e = lire(racine / "traces" / "evaluations")
    print("Bilan des traces de ce dépôt")
    if not appels and not evaluations:
        print("Aucune trace pour l'instant : chaque uv run kit agent et chaque uv run kit evaluer en écrit une.")
    else:
        afficher_jours(par_jour(appels, evaluations))
        if evaluations:
            afficher_evaluations(evaluations, racine)
        print("Coûts estimés aux tarifs de kit/reglages.toml : le relevé exact est dans la console d'Anthropic.")
    if illisibles_a + illisibles_e:
        print(f"{illisibles_a + illisibles_e} fichier(s) de traces/ ne se lisent pas comme une trace : laissés de côté.")
    afficher_non_poussees(racine)
    return 0

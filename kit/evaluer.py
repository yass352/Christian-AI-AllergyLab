"""Le harnais d'évaluation : `uv run kit evaluer` et `uv run kit noter` (SPEC § 5.4).

evaluer fait passer une batterie de questions à l'agent de l'équipe, une à
une, par la même fonction repondre(question) que `kit agent`. Si la batterie
porte son corrigé, il note chaque réponse ; sinon, il enregistre seulement,
et `kit noter` note plus tard, à partir de la trace et d'un corrigé.

Une batterie est un fichier TOML, une table [[question]] par question :

    [[question]]
    id = "q01"
    texte = "…"
    type = "nombre"      # nombre | choix | sans-reponse
    attendu = 12         # absent pour sans-reponse
    tolerance = 0        # pour nombre seulement ; 0 si absente

Pour choix, attendu est un texte, ou une liste des textes acceptés. Une
batterie sans corrigé n'a que id et texte ; un corrigé a id, type, attendu,
tolerance, et pas de texte. Les batteries de kit/exemple/ portent sur la
table inventée : evaluer la fait rendre par charger() à leur place.

La notation est mécanique : aucun modèle ne juge une réponse.

- Question qui a une réponse : juste si la valeur convient, faux sinon,
  abstention à tort si l'agent s'abstient.
- Question sans réponse : abstention fondée, ou réponse inventée.
- Sortie hors contrat : illisible. Exception ou erreur du modèle : erreur.
- nombre : la valeur est un nombre, à tolerance au plus de attendu.
  choix : la valeur est un texte, le même à la casse et aux espaces de bord près.

Trois mesures, affichées ensemble, jamais combinées : la justesse (justes
sur questions qui ont une réponse), l'abstention (abstentions fondées sur
questions sans réponse), la frugalité (jetons, coût estimé, durée). Illisible
et erreur comptent au dénominateur de leur score.
"""

import contextlib
import hashlib
import io
import json
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

from kit import donnees, pousser, traces
from kit.cle import CleAbsente
from kit.donnees import RACINE
from kit.reponse import ReponseIllisible, est_nombre, valider

DOSSIER_EXEMPLE = RACINE / "kit" / "exemple"
BATTERIE_EXEMPLE = DOSSIER_EXEMPLE / "questions.toml"

TYPES = ("nombre", "choix", "sans-reponse")
CLES = ("id", "texte", "type", "attendu", "tolerance")

# Les sept verdicts : tels qu'écrits dans la trace, puis tels qu'affichés.
VERDICTS = {
    "juste": "juste",
    "faux": "faux",
    "abstention-fondee": "abstention fondée",
    "abstention-a-tort": "abstention à tort",
    "reponse-inventee": "réponse inventée",
    "illisible": "illisible",
    "erreur": "erreur",
}


class BatterieInvalide(ValueError):
    """Un fichier de questions, ou un corrigé, qui ne respecte pas le format."""


@dataclass
class Batterie:
    chemin: Path
    questions: list  # {"id", "texte"} pour chaque question, dans l'ordre du fichier
    corrige: dict | None  # {id: {"type", "attendu", "tolerance"}}, ou None sans corrigé
    empreinte: str

    @property
    def exemple(self):
        """Vrai pour une batterie de kit/exemple/ : elle porte sur la table inventée."""
        return self.chemin.resolve().is_relative_to(DOSSIER_EXEMPLE.resolve())


# --- Lire une batterie, ou un corrigé ---------------------------------------------


def lire_questions(chemin):
    """Les tables [[question]] d'un fichier TOML, et l'empreinte du fichier."""
    try:
        octets = Path(chemin).read_bytes()
        contenu = tomllib.loads(octets.decode("utf-8"))
    except FileNotFoundError:
        raise BatterieInvalide("le fichier est introuvable.") from None
    except (OSError, UnicodeDecodeError):
        raise BatterieInvalide("le fichier ne se lit pas comme un texte UTF-8.") from None
    except tomllib.TOMLDecodeError as erreur:
        raise BatterieInvalide(f"ce n'est pas du TOML valide ({erreur}).") from None
    questions = contenu.get("question")
    if set(contenu) != {"question"} or not isinstance(questions, list) or not questions:
        raise BatterieInvalide("il faut une table [[question]] par question, et rien d'autre.")
    # Les fins de ligne ramenées à \n : une même batterie a la même empreinte sur les trois systèmes.
    empreinte = hashlib.sha256(octets.replace(b"\r\n", b"\n")).hexdigest()[:16]
    return questions, empreinte


def lire_corrige_de(question, nom):
    """Le corrigé d'une question, vérifié : {"type", "attendu", "tolerance"} ; None si elle n'en porte pas."""
    type_, attendu, tolerance = (question.get(cle) for cle in ("type", "attendu", "tolerance"))
    if type_ is None:
        if attendu is not None or tolerance is not None:
            raise BatterieInvalide(f"{nom} a un attendu ou une tolérance, mais pas de type.")
        return None
    if type_ not in TYPES:
        raise BatterieInvalide(f"{nom} a le type {type_!r} ; les types sont {', '.join(TYPES)}.")
    if type_ == "sans-reponse":
        if attendu is not None or tolerance is not None:
            raise BatterieInvalide(f"{nom} est sans réponse : ni attendu, ni tolérance.")
    elif type_ == "nombre":
        if not est_nombre(attendu):
            raise BatterieInvalide(f"{nom} est de type nombre : son attendu est un nombre.")
        tolerance = 0 if tolerance is None else tolerance
        if not est_nombre(tolerance) or tolerance < 0:
            raise BatterieInvalide(f"{nom} : la tolérance est un nombre positif ou nul.")
    else:
        acceptes = attendu if isinstance(attendu, list) else [attendu]
        if not acceptes or not all(isinstance(texte, str) and texte.strip() for texte in acceptes):
            raise BatterieInvalide(f"{nom} est de type choix : son attendu est un texte, ou une liste de textes.")
        if tolerance is not None:
            raise BatterieInvalide(f"{nom} est de type choix : pas de tolérance.")
    return {"type": type_, "attendu": attendu, "tolerance": tolerance}


def lire(chemin, corrige_seul=False):
    """Lit une batterie (ou, avec corrige_seul, un corrigé). Lève BatterieInvalide, avec la raison."""
    questions, empreinte = lire_questions(chemin)
    lues, corriges = [], {}
    for rang, question in enumerate(questions, 1):
        ident = question.get("id") if isinstance(question, dict) else None
        if not isinstance(ident, str) or not ident.strip():
            raise BatterieInvalide(f"la question n° {rang} n'a pas d'identifiant (id = \"…\").")
        nom = f"la question {ident}"
        if any(ident == q["id"] for q in lues):
            raise BatterieInvalide(f"deux questions ont l'identifiant {ident}.")
        inconnues = [cle for cle in question if cle not in CLES]
        if inconnues:
            raise BatterieInvalide(f"{nom} a une clé inconnue : {', '.join(inconnues)} ; les clés sont {', '.join(CLES)}.")
        texte = question.get("texte")
        if not corrige_seul and not (isinstance(texte, str) and texte.strip()):
            raise BatterieInvalide(f"{nom} n'a pas de texte (texte = \"…\").")
        corrige = lire_corrige_de(question, nom)
        if corrige_seul and corrige is None:
            raise BatterieInvalide(f"{nom} n'a pas de type : un corrigé donne le type de chaque question.")
        if corrige is not None:
            corriges[ident] = corrige
        lues.append({"id": ident, "texte": texte})
    if corriges and len(corriges) != len(lues):
        raise BatterieInvalide("une batterie porte le corrigé de toutes ses questions, ou d'aucune.")
    return Batterie(Path(chemin), lues, corriges or None, empreinte)


# --- Noter ------------------------------------------------------------------------


def convient(valeur, corrige):
    """Vrai si la valeur rendue convient au corrigé d'une question qui a une réponse."""
    if corrige["type"] == "nombre":
        return est_nombre(valeur) and abs(valeur - corrige["attendu"]) <= corrige["tolerance"]
    acceptes = corrige["attendu"] if isinstance(corrige["attendu"], list) else [corrige["attendu"]]
    return isinstance(valeur, str) and valeur.strip().casefold() in {t.strip().casefold() for t in acceptes}


def juger(resultat, corrige):
    """Le verdict d'une question, à partir de ce que la trace en garde : sa réponse et son erreur."""
    erreur = resultat.get("erreur")
    if erreur is not None:
        return "illisible" if str(erreur).startswith(ReponseIllisible.__name__) else "erreur"
    try:
        reponse = valider(resultat.get("reponse"))
    except ReponseIllisible:
        return "illisible"
    sans_reponse = corrige["type"] == "sans-reponse"
    if reponse["statut"] == "abstention":
        return "abstention-fondee" if sans_reponse else "abstention-a-tort"
    if sans_reponse:
        return "reponse-inventee"
    return "juste" if convient(reponse["valeur"], corrige) else "faux"


def scores(questions, corriges):
    """Les deux scores et le décompte des verdicts de questions déjà jugées. Chacun reste à part."""
    avec = [q for q in questions if corriges[q["id"]]["type"] != "sans-reponse"]
    sans = [q for q in questions if corriges[q["id"]]["type"] == "sans-reponse"]
    return {
        "justesse": {"justes": sum(q["verdict"] == "juste" for q in avec), "sur": len(avec)},
        "abstention": {"fondees": sum(q["verdict"] == "abstention-fondee" for q in sans), "sur": len(sans)},
        "verdicts": {verdict: sum(q["verdict"] == verdict for q in questions) for verdict in VERDICTS},
    }


def frugalite(questions):
    """Jetons lus (en entrée) et écrits (en sortie), coût estimé et durée : au total, puis par question."""
    def somme(lire):
        return sum(lire(q) or 0 for q in questions)

    lus = somme(lambda q: (q.get("jetons") or {}).get("entree"))
    ecrits = somme(lambda q: (q.get("jetons") or {}).get("sortie"))
    cout, duree = somme(lambda q: q.get("cout_estime")), somme(lambda q: q.get("duree_s"))
    nombre = len(questions)
    return {
        "questions": nombre,
        "total": {"jetons": {"entree": lus, "sortie": ecrits}, "cout_estime": round(cout, 8), "duree_s": round(duree, 2)},
        "par_question": None if nombre == 0 else {
            "jetons": {"entree": round(lus / nombre, 1), "sortie": round(ecrits / nombre, 1)},
            "cout_estime": round(cout / nombre, 8),
            "duree_s": round(duree / nombre, 2),
        },
    }


# --- Afficher ---------------------------------------------------------------------


def milliers(nombre):
    return f"{nombre:,}".replace(",", " ").replace(".", ",")


def en_dollars(montant):
    """La même forme que modele.en_dollars, sans charger litellm : noter et bilan restent rapides."""
    return f"{montant:.{4 if montant >= 0.01 else 6}f} $".replace(".", ",")


def secondes(duree):
    return f"{duree:.1f} s".replace(".", ",")


def score(mesure, nom):
    """« 2/3 (67 %) » ; « sans objet » si aucune question ne compte ; « non notée » sans corrigé."""
    if mesure is None:
        return "non notée"
    if mesure["sur"] == 0:
        return "sans objet"
    return f"{mesure[nom]}/{mesure['sur']} ({round(100 * mesure[nom] / mesure['sur'])} %)"


def afficher_mesures(mesures):
    """Les trois mesures, l'une sous l'autre, chacune avec sa définition. Aucune n'est combinée aux autres."""
    print(f"  Justesse     {score(mesures['justesse'], 'justes'):<15} réponses justes, sur les questions qui ont une réponse")
    print(f"  Abstention   {score(mesures['abstention'], 'fondees'):<15} abstentions fondées, sur les questions sans réponse")
    frugal = mesures["frugalite"]
    for nom, part in (("au total", frugal["total"]), ("par question", frugal["par_question"])):
        if part is None:
            continue
        print(
            f"  {'Frugalité' if nom == 'au total' else '':<12} {nom:<15} {milliers(round(part['jetons']['entree']))} "
            f"jetons lus, {milliers(round(part['jetons']['sortie']))} écrits, {en_dollars(part['cout_estime'])}, "
            f"{secondes(part['duree_s'])}"
        )
    if mesures["verdicts"]:
        decompte = ", ".join(f"{VERDICTS[v]} {n}" for v, n in mesures["verdicts"].items() if n)
        print(f"  Verdicts     {decompte}")


def apercu(resultat):
    """Ce que l'agent a rendu, sur une ligne courte."""
    erreur = resultat.get("erreur")
    if erreur is not None:
        nature, _, texte = str(erreur).partition(" : ")
        if nature == ReponseIllisible.__name__:
            return f"illisible : {texte[:90]}"
        return f"erreur : {str(erreur)[:90]}"
    try:
        reponse = valider(resultat.get("reponse"))
    except ReponseIllisible as illisible:
        return f"illisible : {illisible}"
    if reponse["statut"] == "abstention":
        return "abstention"
    valeur = str(reponse["valeur"])
    return f"réponse : {valeur if len(valeur) <= 40 else valeur[:40] + '…'}"


def afficher_question(resultat):
    """La ligne d'une question traitée, affichée aussitôt : la salle voit la batterie avancer."""
    morceaux = [apercu(resultat)]
    if resultat.get("verdict"):
        morceaux.append(VERDICTS[resultat["verdict"]])
    jetons = resultat["jetons"]
    morceaux += [
        f"{milliers(jetons['entree'])} jetons lus, {milliers(jetons['sortie'])} écrits",
        en_dollars(resultat["cout_estime"]),
        secondes(resultat["duree_s"]),
    ]
    print(f"        {' | '.join(morceaux)}", flush=True)


def relatif(chemin, racine=RACINE):
    """Le chemin, relatif au dépôt s'il y est (racine, puis le dossier du kit), en notation /."""
    chemin = Path(chemin).resolve()
    for base in (racine, RACINE):
        if chemin.is_relative_to(base.resolve()):
            return chemin.relative_to(base.resolve()).as_posix()
    return chemin.as_posix()


# --- Faire passer une batterie ----------------------------------------------------


def faire_passer(texte, racine, detail):
    """Pose une question à l'agent. Rend son résultat, et l'erreur qui doit arrêter la batterie, ou None."""
    from kit import modele, question  # importés ici : litellm est long à charger, et noter s'en passe

    modele.journal_neuf()
    chrono = time.monotonic()
    reponse, erreur = None, None
    # Sans --detail, ce que l'agent affiche à chaque étape est mis de côté : ses étapes sont dans la trace.
    sortie_agent = contextlib.nullcontext() if detail else contextlib.redirect_stdout(io.StringIO())
    try:
        with sortie_agent:
            sortie = question.charger_repondre(racine)(texte)
        if modele.journal["erreur"]:  # une erreur finale que smolagents a avalée
            raise modele.journal["erreur"]
        reponse = sortie  # gardée telle quelle si elle ne respecte pas le contrat
        reponse = valider(sortie)
    except KeyboardInterrupt as interruption:
        erreur = interruption
    except Exception as exception:
        erreur = question.erreur_prevue(exception) or exception
    resultat = {
        "texte": texte,
        "reponse": reponse,
        "etapes": list(modele.journal["etapes"]),
        "jetons": dict(modele.journal["jetons"]),
        "cout_estime": modele.journal["cout_estime"],
        "duree_s": round(time.monotonic() - chrono, 2),
        "erreur": None if erreur is None else traces.decrire(erreur),
    }
    # Une erreur qui vaudrait pour toutes les questions suivantes arrête la batterie.
    arret = erreur if isinstance(erreur, (KeyboardInterrupt, modele.CagnotteEpuisee, CleAbsente)) else None
    return resultat, arret


def mesurer(questions, corriges):
    """Les champs de mesure d'une trace : scores et verdicts (None sans corrigé), frugalité."""
    notes = scores(questions, corriges) if corriges else {"justesse": None, "abstention": None, "verdicts": None}
    return {**notes, "frugalite": frugalite(questions)}


def passer(batterie, nom_modele, officielle, detail, racine):
    """Fait passer une batterie et écrit sa trace. Rend (code de sortie, vrai si la suite doit s'arrêter)."""
    from kit import modele

    identifiant = modele.choisi(nom_modele)["identifiant"]
    table = donnees.EXEMPLE if batterie.exemple else donnees.FICHIER
    nombre = len(batterie.questions)
    print(f"Batterie {relatif(batterie.chemin, racine)} : {nombre} question{'s' if nombre > 1 else ''}, "
          f"{'avec son corrigé' if batterie.corrige else 'sans corrigé'}")
    print(f"  table : {relatif(table, racine)}{' (table inventée)' if batterie.exemple else ''} | "
          f"modèle : {identifiant} ({nom_modele}){' | passe officielle' if officielle else ''}")
    arret, trace = None, None
    try:
        with traces.evaluation(
            racine, officielle=officielle, modele=identifiant, table=relatif(table, racine),
            batterie={"chemin": relatif(batterie.chemin, racine), "empreinte": batterie.empreinte, "questions": nombre},
        ) as trace:
            resultats = trace.champs["questions"]
            try:
                with donnees.utiliser(table):
                    for rang, question in enumerate(batterie.questions, 1):
                        print(f"  [{rang}/{nombre}] {question['id']} : {question['texte']}", flush=True)
                        resultat, arret = faire_passer(question["texte"], racine, detail)
                        resultat = {"id": question["id"], **resultat}
                        if batterie.corrige:
                            resultat["verdict"] = juger(resultat, batterie.corrige[question["id"]])
                        resultats.append(resultat)
                        afficher_question(resultat)
                        if isinstance(arret, KeyboardInterrupt):
                            raise arret
                        if arret is not None:
                            trace.noter(erreur=traces.decrire(arret))
                            break
            finally:
                trace.noter(**mesurer(resultats, batterie.corrige))
    finally:
        if trace is not None and trace.chemin is not None:
            conclure(trace, arret, racine)
    sans_contrat = sum(q["erreur"] is not None for q in trace.champs["questions"])
    return (0 if arret is None and sans_contrat == 0 else 1), arret is not None


def conclure(trace, arret, racine):
    """Après la batterie : pourquoi elle s'est arrêtée, les trois mesures, le chemin de la trace."""
    champs = trace.champs
    if isinstance(arret, KeyboardInterrupt):
        print("  Batterie interrompue : la trace garde les questions déjà traitées.")
    elif arret is not None:
        print(f"  Batterie arrêtée : {arret.texte[0].upper() + arret.texte[1:]}")
        print(f"  Que faire : {arret.que_faire}")
    sans_contrat = sum(q["erreur"] is not None for q in champs["questions"])
    if sans_contrat and arret is None:
        print(f"  {sans_contrat} question{'s' if sans_contrat > 1 else ''} sans réponse conforme au contrat : "
              "le détail, étapes comprises, est dans la trace.")
    afficher_mesures(champs)
    if champs["justesse"] is None:
        print("  Pour noter : uv run kit noter <trace> --corrige <corrigé.toml>")
    print(f"Trace : {relatif(trace.chemin, racine)}")


def choisir(batteries, exemple, racine):
    """Les fichiers à faire passer : ceux donnés, la batterie d'exemple, ou toutes celles de equipe/questions/."""
    if batteries:
        chemins = [Path(chemin) for chemin in batteries]
        if exemple and not all(c.resolve().is_relative_to(DOSSIER_EXEMPLE.resolve()) for c in chemins):
            raise BatterieInvalide(
                "--exemple fait passer une batterie de kit/exemple/, sur la table inventée. "
                "Pour une batterie de ton équipe, lance la commande sans --exemple."
            )
        return chemins
    if exemple:
        return [BATTERIE_EXEMPLE]
    return sorted(c for c in (racine / "equipe" / "questions").glob("*.toml") if not c.name.startswith("."))


def refus_officielle(racine):
    """Pourquoi une passe officielle ne peut pas partir d'ici ; None si equipe/ est enregistré et poussé.

    Aucune connexion : la comparaison porte sur ce que git sait déjà du dépôt de l'équipe.
    """
    que_faire = "enregistre et pousse ton travail (git add equipe, git commit, git push), puis relance la commande."
    if pousser.git(racine, "--version") is None:
        return f"git est introuvable : une passe officielle exige un travail poussé sur GitHub. {pousser.GIT_ABSENT}"
    if pousser.dossier_git(racine) is None:
        return "ce dossier n'est pas un dépôt git : une passe officielle exige un travail poussé sur GitHub."
    modifs = pousser.git(racine, "status", "--porcelain", "--untracked-files=all", "--", "equipe")
    if modifs.returncode != 0 or modifs.stdout.strip():
        return f"equipe/ a des modifications non enregistrées. Que faire : {que_faire}"
    if pousser.git(racine, "rev-parse", "--verify", "--quiet", "@{u}").returncode != 0:
        return pousser.SANS_BRANCHE_SUIVIE
    non_pousses = pousser.git(racine, "rev-list", "--count", "@{u}..HEAD", "--", "equipe")
    if non_pousses.returncode != 0 or non_pousses.stdout.strip() != "0":
        return f"des commits qui touchent equipe/ ne sont pas encore poussés. Que faire : {que_faire}"
    return None


def evaluer(batteries=(), exemple=False, nom_modele="developpement", officielle=False, detail=False, racine=RACINE):
    """`uv run kit evaluer` : fait passer chaque batterie, l'une après l'autre. Rend 0 ou 1.

    0 : toutes les batteries sont allées au bout, et chaque question a reçu une
    réponse conforme au contrat, juste ou non. 1 sinon.
    """
    from kit import modele

    if nom_modele not in modele.REGLAGES["modeles"]:
        noms = ", ".join(modele.REGLAGES["modeles"])
        print(f"Modèle inconnu : {nom_modele}. Ceux de kit/reglages.toml : {noms}.")
        return 1
    try:
        chemins = choisir(batteries, exemple, racine)
    except BatterieInvalide as erreur:
        print(erreur)
        return 1
    if not chemins:
        print(
            "Aucune batterie dans equipe/questions/. Que faire : écris-en une, un fichier .toml par lot, "
            "sur le modèle de kit/exemple/questions.toml ; ou lance uv run kit evaluer --exemple."
        )
        return 1
    lues, defauts = [], []
    for chemin in chemins:
        try:
            lues.append(lire(chemin))
        except BatterieInvalide as erreur:
            defauts.append(f"La batterie {relatif(chemin, racine)} ne se lit pas : {erreur}")
    if defauts:  # rien ne part tant qu'une batterie est mal écrite : aucun jeton dépensé pour rien
        print("\n".join(defauts))
        print("Que faire : corrige le fichier, sur le modèle de kit/exemple/questions.toml, puis relance.")
        return 1
    if officielle:
        refus = refus_officielle(racine)
        if refus:
            print(f"Passe officielle refusée : {refus}")
            return 1
    avant, modele.en_cours = modele.en_cours, nom_modele
    code = 0
    try:
        for batterie in lues:
            code_batterie, arreter = passer(batterie, nom_modele, officielle, detail, racine)
            code = max(code, code_batterie)
            if arreter:
                break
    finally:
        modele.en_cours = avant
    return code


# --- Noter après coup -------------------------------------------------------------


def lire_trace(chemin):
    """Une trace d'évaluation. Lève ValueError, avec la raison, si le fichier n'en est pas une."""
    try:
        trace = json.loads(Path(chemin).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError("le fichier est introuvable.") from None
    except (OSError, UnicodeDecodeError, ValueError):
        raise ValueError("le fichier ne se lit pas comme du JSON.") from None
    if not isinstance(trace, dict) or trace.get("format") != traces.FORMAT_EVALUATION or not isinstance(
        trace.get("questions"), list
    ) or "batterie" not in trace:
        raise ValueError("ce n'est pas une trace d'évaluation (elles sont dans traces/evaluations/).")
    return trace


def noter(chemin_trace, chemin_corrige, en_json=False):
    """`uv run kit noter` : relit une trace et un corrigé, affiche verdicts et mesures. N'écrit rien."""
    try:
        trace = lire_trace(chemin_trace)
    except ValueError as erreur:
        print(f"La trace {chemin_trace} ne se lit pas : {erreur}")
        return 1
    try:
        corriges = lire(chemin_corrige, corrige_seul=True).corrige
    except BatterieInvalide as erreur:
        print(f"Le corrigé {chemin_corrige} ne se lit pas : {erreur}")
        return 1
    questions = [q for q in trace["questions"] if isinstance(q, dict)]
    manquantes = [str(q.get("id")) for q in questions if q.get("id") not in corriges]
    if manquantes:
        print(f"Le corrigé ne dit rien de {', '.join(manquantes)} : ce n'est pas le corrigé de cette batterie.")
        return 1
    jugees = [{**q, "verdict": juger(q, corriges[q["id"]])} for q in questions]
    mesures = mesurer(jugees, corriges)
    if en_json:
        print(json.dumps({
            "trace": Path(chemin_trace).as_posix(), "corrige": Path(chemin_corrige).as_posix(),
            "questions": [{"id": q["id"], "verdict": q["verdict"]} for q in jugees], **mesures,
        }, ensure_ascii=False))
        return 0
    batterie = trace["batterie"] or {}
    print(f"Notation de la trace {Path(chemin_trace).as_posix()}, avec le corrigé {Path(chemin_corrige).as_posix()}")
    print(f"  batterie : {batterie.get('chemin')} | table : {trace.get('table')} | modèle : {trace.get('modele')}")
    for q in jugees:
        print(f"  {q['id']:<12} {VERDICTS[q['verdict']]:<19} {apercu(q)}")
    if trace.get("erreur"):
        print(f"  La batterie s'est arrêtée avant la fin : {str(trace['erreur'])[:120]}")
    afficher_mesures(mesures)
    print("Rien n'a été écrit : la trace reste telle quelle.")
    return 0

"""Le harnais d'évaluation : batteries, sept verdicts, trois mesures jamais combinées, noter, bilan.

Un faux agent répond à la place de equipe/agent.py : il rend, pour chaque
question, la sortie que le test a prévue. Quand un test a besoin de jetons,
le faux modèle de conftest.py joue l'API, sans réseau. Aucune clé réelle,
aucune question sur le fichier publié : les batteries de ces tests portent
sur la table inventée, ou sur rien du tout. Tout s'écrit sous un dossier
temporaire, jamais dans traces/ du kit.
"""

import json
import shutil
import subprocess
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from kit import bilan, cli, donnees, evaluer, modele, pousser, question, traces
from kit.donnees import RACINE

from conftest import agent_boucle_maison, erreur, message

CORRIGE_EXEMPLE = RACINE / "kit" / "exemple" / "corrige.toml"
SANS_CORRIGE_EXEMPLE = RACINE / "kit" / "exemple" / "questions-sans-corrige.toml"
LIMITE = "You have reached your specified workspace API usage limits."


# --- Outils -------------------------------------------------------------------


def ecrire_batterie(chemin, questions):
    """Écrit une batterie TOML. Les valeurs s'écrivent comme en JSON, que TOML lit de la même façon."""
    lignes = []
    for q in questions:
        lignes.append("[[question]]")
        lignes += [f"{cle} = {json.dumps(valeur, ensure_ascii=False)}" for cle, valeur in q.items()]
        lignes.append("")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(lignes), encoding="utf-8")
    return chemin


class FauxAgent:
    """Rend, pour chaque texte de question, la sortie prévue ; une exception prévue est levée."""

    def __init__(self, sorties):
        self.sorties = sorties
        self.questions = []  # les questions reçues, dans l'ordre

    def __call__(self, texte):
        self.questions.append(texte)
        sortie = self.sorties[texte]
        if callable(sortie):
            sortie = sortie()
        if isinstance(sortie, BaseException):
            raise sortie
        return sortie


@pytest.fixture
def brancher_agent(monkeypatch):
    """brancher_agent(agent) : evaluer appellera agent au lieu de la fonction repondre de equipe/agent.py."""
    def brancher(agent):
        monkeypatch.setattr(question, "charger_repondre", lambda racine: agent)
        return agent

    return brancher


def reponse(valeur, justification="Une réponse prévue par le test."):
    return {"statut": "reponse", "valeur": valeur, "justification": justification}


ABSTENTION = {"statut": "abstention", "valeur": None, "justification": "Je ne peux pas conclure."}


def fichiers(dossier):
    return sorted(dossier.rglob("*.json")) if dossier.exists() else []


def trace_unique(racine):
    (chemin,) = fichiers(racine / "traces" / "evaluations")
    return chemin, json.loads(chemin.read_text(encoding="utf-8"))


def nouvelle_trace(racine, deja):
    """La trace d'évaluation écrite depuis deja : deux traces d'une même seconde ne se rangent pas par ordre d'écriture."""
    (chemin,) = set(fichiers(racine / "traces" / "evaluations")) - set(deja)
    return chemin, json.loads(chemin.read_text(encoding="utf-8"))


def contenu(dossier):
    return {f.relative_to(dossier).as_posix(): f.read_bytes() for f in dossier.rglob("*") if f.is_file()}


def agent_de_la_table():
    """Un faux agent qui lit la table par charger(), comme le ferait celui de l'équipe, et répond juste."""
    def repondre(texte):
        tableau = donnees.charger()
        if "âge moyen" in texte:
            return reponse(float(tableau["Age"].mean()))
        if "plus âgé" in texte:
            return reponse(str(tableau.loc[tableau["Age"].idxmax(), "Chip_Type"]))
        assert "EX13" not in set(tableau["Patient_ID"])
        return ABSTENTION

    return repondre


# Sept questions, une par verdict, et ce que le faux agent y rend.
SEPT = [
    ({"id": "juste", "texte": "Combien ?", "type": "nombre", "attendu": 12}, reponse(12)),
    ({"id": "faux", "texte": "Combien encore ?", "type": "nombre", "attendu": 12, "tolerance": 1}, reponse(14)),
    ({"id": "a-tort", "texte": "Quelle puce ?", "type": "choix", "attendu": "ALEX"}, ABSTENTION),
    ({"id": "fondee", "texte": "Quel poids ?", "type": "sans-reponse"}, ABSTENTION),
    ({"id": "inventee", "texte": "Quelle taille ?", "type": "sans-reponse"}, reponse("deptA")),
    ({"id": "illisible", "texte": "Combien de puces ?", "type": "nombre", "attendu": 3}, "trois"),
    ({"id": "erreur", "texte": "Quel département ?", "type": "choix", "attendu": "deptB"}, RuntimeError("panne")),
]


# --- Les cas nommés par le prompt -------------------------------------------------------


def test_sept_verdicts(depot, brancher_agent, capsys):
    batterie = ecrire_batterie(depot / "equipe" / "questions" / "lot1.toml", [q for q, _ in SEPT])
    brancher_agent(FauxAgent({q["texte"]: sortie for q, sortie in SEPT}))

    # 1 : deux questions n'ont pas reçu de réponse conforme au contrat (illisible, erreur).
    assert evaluer.evaluer([batterie], racine=depot) == 1

    _, trace = trace_unique(depot)
    assert {q["id"]: q["verdict"] for q in trace["questions"]} == {
        "juste": "juste", "faux": "faux", "a-tort": "abstention-a-tort", "fondee": "abstention-fondee",
        "inventee": "reponse-inventee", "illisible": "illisible", "erreur": "erreur",
    }
    assert trace["verdicts"] == {verdict: 1 for verdict in evaluer.VERDICTS}
    # Illisible et erreur comptent au dénominateur : cinq questions ont une réponse, deux n'en ont pas.
    assert trace["justesse"] == {"justes": 1, "sur": 5}
    assert trace["abstention"] == {"fondees": 1, "sur": 2}
    sortie = capsys.readouterr().out
    for affiche in evaluer.VERDICTS.values():
        assert f"| {affiche} |" in sortie
    assert "illisible : l'agent a rendu un texte" in sortie and "erreur : RuntimeError : panne" in sortie


@pytest.mark.parametrize("valeur, corrige, juste", [
    (12, {"type": "nombre", "attendu": 12, "tolerance": 0}, True),
    (12.0, {"type": "nombre", "attendu": 12, "tolerance": 0}, True),
    (12.4, {"type": "nombre", "attendu": 12, "tolerance": 0}, False),
    (12.4, {"type": "nombre", "attendu": 12, "tolerance": 0.5}, True),
    (11.5, {"type": "nombre", "attendu": 12, "tolerance": 0.5}, True),
    (11.4, {"type": "nombre", "attendu": 12, "tolerance": 0.5}, False),
    ("12", {"type": "nombre", "attendu": 12, "tolerance": 0}, False),  # un texte n'est pas un nombre
    ("  isac_v2 ", {"type": "choix", "attendu": "ISAC_V2", "tolerance": None}, True),
    ("ISAC V2", {"type": "choix", "attendu": ["ISAC_V2", "ISAC V2"], "tolerance": None}, True),
    ("ISAC_V1", {"type": "choix", "attendu": ["ISAC_V2", "ISAC V2"], "tolerance": None}, False),
    ("ISACV2", {"type": "choix", "attendu": "ISAC_V2", "tolerance": None}, False),  # seuls les bords comptent
    (2, {"type": "choix", "attendu": "2", "tolerance": None}, False),  # un nombre n'est pas un texte
])
def test_comparaison_mecanique(valeur, corrige, juste):
    assert evaluer.convient(valeur, corrige) is juste
    assert evaluer.juger({"reponse": reponse(valeur), "erreur": None}, corrige) == ("juste" if juste else "faux")


def test_scores_jamais_combines(depot, brancher_agent, capsys):
    questions = [q for q, _ in SEPT[:5]]
    batterie = ecrire_batterie(depot / "lot.toml", questions)
    brancher_agent(FauxAgent({q["texte"]: sortie for q, sortie in SEPT}))
    assert evaluer.evaluer([batterie], racine=depot) == 0

    chemin, trace = trace_unique(depot)
    # Trois mesures, chacune dans son champ, et rien qui les réunisse.
    assert tuple(trace) == traces.CHAMPS_EVALUATION
    assert trace["justesse"] == {"justes": 1, "sur": 3}
    assert trace["abstention"] == {"fondees": 1, "sur": 2}
    assert set(trace["frugalite"]) == {"questions", "total", "par_question"}
    sortie = capsys.readouterr().out
    assert "Justesse     1/3 (33 %)" in sortie and "Abstention   1/2 (50 %)" in sortie
    assert sortie.count("%") == 2  # les deux scores, et aucun pourcentage qui les combine

    # Pareil pour noter, en clair et sur une ligne.
    corrige = ecrire_batterie(depot / "corrige.toml", [{k: v for k, v in q.items() if k != "texte"} for q in questions])
    assert evaluer.noter(chemin, corrige, en_json=True) == 0
    resultat = json.loads(capsys.readouterr().out)
    assert set(resultat) == {"trace", "corrige", "questions", "justesse", "abstention", "verdicts", "frugalite"}
    assert (resultat["justesse"], resultat["abstention"]) == (trace["justesse"], trace["abstention"])
    assert evaluer.noter(chemin, corrige) == 0
    assert capsys.readouterr().out.count("%") == 2

    # Dénominateur nul : « sans objet », jamais un zéro qui ferait baisser une moyenne.
    seules = ecrire_batterie(depot / "seules.toml", questions[:2])
    assert evaluer.evaluer([seules], racine=depot) == 0
    assert "Abstention   sans objet" in capsys.readouterr().out
    bilan.bilan(depot)
    sortie = capsys.readouterr().out
    assert "justesse 1/3 (33 %) | abstention 1/2 (50 %)" in sortie
    assert "justesse 1/2 (50 %) | abstention sans objet" in sortie


def test_frugalite(depot, faux_modele, cle_enregistree, brancher_agent, monkeypatch, capsys):
    batterie = ecrire_batterie(depot / "lot.toml", [
        {"id": "q1", "texte": "Première ?", "type": "nombre", "attendu": 12},
        {"id": "q2", "texte": "Seconde ?", "type": "sans-reponse"},
    ])
    brancher_agent(agent_boucle_maison)  # un vrai moteur du kit, devant le faux modèle
    instants = iter([100.0, 102.0, 102.0, 106.0] * 2)  # deux secondes, puis quatre, à chaque passage
    monkeypatch.setattr(evaluer, "time", SimpleNamespace(monotonic=lambda: next(instants)))

    for nom, cout in (("developpement", 0.0007), ("officiel", 0.014)):
        deja = fichiers(depot / "traces" / "evaluations")
        faux_modele.programmer(
            message(outils=[("final_answer", reponse(12))], entree=1000, sortie=200),
            message(outils=[("final_answer", ABSTENTION)], entree=3000, sortie=400),
        )
        assert evaluer.evaluer([batterie], nom_modele=nom, racine=depot) == 0
        assert modele.en_cours == "developpement"  # rendu tel quel après la batterie

        _, trace = nouvelle_trace(depot, deja)
        assert trace["modele"] == modele.choisi(nom)["identifiant"]
        assert [q["jetons"] for q in trace["questions"]] == [
            {"entree": 1000, "sortie": 200}, {"entree": 3000, "sortie": 400},
        ]
        assert [q["duree_s"] for q in trace["questions"]] == [2.0, 4.0]
        frugal = trace["frugalite"]
        assert frugal["questions"] == 2
        assert frugal["total"]["jetons"] == {"entree": 4000, "sortie": 600}
        assert frugal["total"]["cout_estime"] == pytest.approx(cout)
        assert frugal["total"]["duree_s"] == 6.0
        assert frugal["par_question"]["jetons"] == {"entree": 2000, "sortie": 300}
        assert frugal["par_question"]["cout_estime"] == pytest.approx(cout / 2)
        assert frugal["par_question"]["duree_s"] == 3.0
        sortie = capsys.readouterr().out
        total, par_question = evaluer.en_dollars(cout), evaluer.en_dollars(cout / 2)
        assert f"Frugalité    au total        4 000 jetons lus, 600 écrits, {total}, 6,0 s" in sortie
        assert f"par question    2 000 jetons lus, 300 écrits, {par_question}, 3,0 s" in sortie
        assert "1 000 jetons lus, 200 écrits" in sortie  # la ligne de la première question
    assert faux_modele.appels == 4


def test_batterie_sans_corrige(depot, brancher_agent, capsys):
    brancher_agent(agent_de_la_table())

    # Une batterie de kit/exemple/ porte sur la table inventée, avec ou sans --exemple.
    assert evaluer.evaluer([SANS_CORRIGE_EXEMPLE], racine=depot) == 0

    _, trace = trace_unique(depot)
    assert trace["table"] == "kit/exemple/mini.csv"
    assert trace["batterie"]["chemin"] == "kit/exemple/questions-sans-corrige.toml"
    assert trace["batterie"]["questions"] == 3 and len(trace["batterie"]["empreinte"]) == 16
    assert [q["id"] for q in trace["questions"]] == ["q01", "q02", "q03"]
    assert all(q["verdict"] is None for q in trace["questions"])
    assert trace["justesse"] is None and trace["abstention"] is None and trace["verdicts"] is None
    assert trace["frugalite"]["questions"] == 3
    assert [q["reponse"]["valeur"] for q in trace["questions"]] == [33.0, "ISAC_V2", None]
    assert donnees.en_cours == donnees.FICHIER  # charger() lit de nouveau le fichier publié
    sortie = capsys.readouterr().out
    assert "Justesse     non notée" in sortie and "Abstention   non notée" in sortie
    assert "Pour noter : uv run kit noter <trace> --corrige <corrigé.toml>" in sortie


@pytest.mark.parametrize("texte, raison", [
    ("", "une table [[question]] par question"),
    ("question = 3\n", "une table [[question]] par question"),
    ('titre = "x"\n[[question]]\nid = "a"\ntexte = "b"\n', "une table [[question]] par question"),
    ('[[question]]\nid = "a\n', "pas du TOML valide"),
    ('[[question]]\ntexte = "b"\n', "n'a pas d'identifiant"),
    ('[[question]]\nid = "a"\n', "n'a pas de texte"),
    ('[[question]]\nid = "a"\ntexte = "b"\n[[question]]\nid = "a"\ntexte = "c"\n', "deux questions"),
    ('[[question]]\nid = "a"\ntexte = "b"\ntype = "nombre"\nattendus = 3\n', "clé inconnue : attendus"),
    ('[[question]]\nid = "a"\ntexte = "b"\ntype = "entier"\nattendu = 3\n', "les types sont"),
    ('[[question]]\nid = "a"\ntexte = "b"\ntype = "nombre"\nattendu = "3"\n', "son attendu est un nombre"),
    ('[[question]]\nid = "a"\ntexte = "b"\ntype = "nombre"\nattendu = 3\ntolerance = -1\n', "positif ou nul"),
    ('[[question]]\nid = "a"\ntexte = "b"\ntype = "choix"\nattendu = []\n', "une liste de textes"),
    ('[[question]]\nid = "a"\ntexte = "b"\ntype = "choix"\nattendu = "x"\ntolerance = 1\n', "pas de tolérance"),
    ('[[question]]\nid = "a"\ntexte = "b"\ntype = "sans-reponse"\nattendu = 3\n', "ni attendu"),
    ('[[question]]\nid = "a"\ntexte = "b"\nattendu = 3\n', "mais pas de type"),
    ('[[question]]\nid = "a"\ntexte = "b"\ntype = "sans-reponse"\n[[question]]\nid = "c"\ntexte = "d"\n',
     "toutes ses questions, ou d'aucune"),
])
def test_batterie_mal_ecrite(texte, raison, depot, brancher_agent, capsys):
    (depot / "equipe" / "questions").mkdir()
    (depot / "equipe" / "questions" / "lot1.toml").write_text(texte, encoding="utf-8")
    ecrire_batterie(depot / "equipe" / "questions" / "lot2.toml", [{"id": "a", "texte": "b"}])
    agent = brancher_agent(FauxAgent({"b": ABSTENTION}))

    assert evaluer.evaluer(racine=depot) == 1

    sortie = capsys.readouterr().out
    assert "La batterie equipe/questions/lot1.toml ne se lit pas" in sortie and raison in sortie
    assert agent.questions == []  # rien ne part tant qu'une batterie est mal écrite
    assert not (depot / "traces" / "evaluations").exists()


def test_noter_apres_coup(depot, brancher_agent, faux_modele, capsys):
    brancher_agent(agent_de_la_table())
    assert evaluer.evaluer([SANS_CORRIGE_EXEMPLE], racine=depot) == 0
    sans_corrige, _ = trace_unique(depot)
    assert evaluer.evaluer(exemple=True, racine=depot) == 0  # la même batterie, avec son corrigé
    _, notee = nouvelle_trace(depot, [sans_corrige])
    capsys.readouterr()
    avant, avant_kit = contenu(depot), contenu(RACINE / "traces")

    assert cli.main(["noter", str(sans_corrige), "--corrige", str(CORRIGE_EXEMPLE), "--json"]) == 0
    ligne = capsys.readouterr().out
    assert ligne.count("\n") == 1
    resultat = json.loads(ligne)
    assert resultat["questions"] == [{"id": q["id"], "verdict": q["verdict"]} for q in notee["questions"]]
    assert [q["verdict"] for q in notee["questions"]] == ["juste", "juste", "abstention-fondee"]
    for mesure in ("justesse", "abstention", "verdicts"):
        assert resultat[mesure] == notee[mesure]

    assert evaluer.noter(sans_corrige, CORRIGE_EXEMPLE) == 0
    sortie = capsys.readouterr().out
    assert "q03          abstention fondée" in sortie
    assert "Justesse     2/2 (100 %)" in sortie and "Abstention   1/1 (100 %)" in sortie
    assert "Rien n'a été écrit" in sortie

    # N'appelle pas le modèle, n'écrit rien, ni dans le dépôt, ni dans traces/ du kit.
    assert faux_modele.appels == 0
    assert contenu(depot) == avant and contenu(RACINE / "traces") == avant_kit

    # Un corrigé qui n'est pas celui de la batterie, une trace qui n'est pas une évaluation.
    autre = ecrire_batterie(depot / "autre.toml", [{"id": "q01", "type": "sans-reponse"}])
    assert evaluer.noter(sans_corrige, autre) == 1
    assert "Le corrigé ne dit rien de q02, q03" in capsys.readouterr().out
    assert evaluer.noter(sans_corrige, SANS_CORRIGE_EXEMPLE) == 1
    assert "un corrigé donne le type de chaque question" in capsys.readouterr().out
    appel = traces.ecrire_appel({"question": "Combien ?"}, depot)
    assert evaluer.noter(appel, CORRIGE_EXEMPLE) == 1
    assert "ce n'est pas une trace d'évaluation" in capsys.readouterr().out


def test_trace_sans_valeur_attendue(depot, brancher_agent):
    # Des réponses fausses : aucune valeur du corrigé n'arrive dans la trace par la bouche de l'agent.
    brancher_agent(FauxAgent({
        "Quel est l'âge moyen des patients de la table ?": reponse(40),
        "Quel est le type de puce (Chip_Type) du patient le plus âgé de la table ?": reponse("ALEX"),
        "Quel âge a le patient EX13 ?": reponse(12),
    }))
    assert evaluer.evaluer(exemple=True, racine=depot) == 0

    chemin, trace = trace_unique(depot)
    assert trace["format"] == traces.FORMAT_EVALUATION
    assert tuple(trace) == traces.CHAMPS_EVALUATION
    assert all(tuple(q) == traces.CHAMPS_QUESTION for q in trace["questions"])
    assert [q["verdict"] for q in trace["questions"]] == ["faux", "faux", "reponse-inventee"]

    def cles(valeur):
        if isinstance(valeur, dict):
            return set(valeur) | set().union(*(cles(v) for v in valeur.values()))
        if isinstance(valeur, list):
            return set().union(*(cles(v) for v in valeur))
        return set()

    assert not cles(trace) & {"type", "attendu", "tolerance"}
    texte = chemin.read_text(encoding="utf-8")
    for absent in ("attendu", "tolerance", "sans-reponse", "ISAC_V2", "ISAC V2", "nombre", "choix"):
        assert absent not in texte


def test_cagnotte_epuisee_arrete_la_batterie(depot, faux_modele, cle_enregistree, brancher_agent, capsys):
    questions = [{"id": f"q{n}", "texte": f"Question {n} ?", "type": "sans-reponse"} for n in (1, 2, 3)]
    ecrire_batterie(depot / "equipe" / "questions" / "lot1.toml", questions)
    ecrire_batterie(depot / "equipe" / "questions" / "lot2.toml", [{"id": "r1", "texte": "Lot 2 ?"}])
    faux_modele.programmer(
        message(outils=[("final_answer", ABSTENTION)]),
        erreur(400, "invalid_request_error", LIMITE),
    )
    brancher_agent(agent_boucle_maison)

    assert evaluer.evaluer(racine=depot) == 1  # sans argument : toutes les batteries de equipe/questions/

    assert faux_modele.appels == 2 and faux_modele.attentes == []  # aucune nouvelle tentative
    _, trace = trace_unique(depot)  # une seule trace : le lot 2 n'a pas commencé
    assert trace["batterie"] == {"chemin": "equipe/questions/lot1.toml", "empreinte": trace["batterie"]["empreinte"],
                                 "questions": 3}
    assert [q["id"] for q in trace["questions"]] == ["q1", "q2"]
    assert [q["verdict"] for q in trace["questions"]] == ["abstention-fondee", "erreur"]
    assert trace["questions"][1]["erreur"].startswith("CagnotteEpuisee : cagnotte épuisée")
    assert trace["erreur"].startswith("CagnotteEpuisee")
    assert trace["abstention"] == {"fondees": 1, "sur": 2}
    sortie = capsys.readouterr().out
    assert "Batterie arrêtée : Cagnotte épuisée" in sortie and "Que faire : va voir Adrien." in sortie
    assert "Question 3 ?" not in sortie and "Lot 2 ?" not in sortie


def test_officielle_refuse_un_etat_non_pousse(depot, tmp_path, brancher_agent, monkeypatch, capsys):
    if shutil.which("git") is None:
        pytest.skip("git absent de cette machine")
    configuration = tmp_path / "gitconfig"
    configuration.write_text("[user]\n\tname = kit\n\temail = kit\n[init]\n\tdefaultBranch = main\n"
                             "[commit]\n\tgpgsign = false\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(configuration))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    def git(*arguments, dossier=depot):
        subprocess.run(["git", *arguments], cwd=dossier, check=True, capture_output=True)

    batterie = ecrire_batterie(depot / "equipe" / "questions" / "lot1.toml", [{"id": "q1", "texte": "Combien ?"}])
    agent = brancher_agent(FauxAgent({"Combien ?": reponse(12)}))

    def refusee(raison):
        assert evaluer.evaluer([batterie], officielle=True, racine=depot) == 1
        assert f"Passe officielle refusée : {raison}" in capsys.readouterr().out
        assert agent.questions == [] and not (depot / "traces" / "evaluations").exists()

    refusee("ce dossier n'est pas un dépôt git")
    git("init", "--quiet", "--bare", str(tmp_path / "distant.git"), dossier=tmp_path)
    git("init", "--quiet")
    git("add", "equipe.toml", "equipe")
    git("commit", "--quiet", "-m", "Départ")
    refusee("la branche de ce dossier n'est reliée à aucune branche")
    git("remote", "add", "origin", str(tmp_path / "distant.git"))
    git("push", "--quiet", "--set-upstream", "origin", "main")

    (depot / "equipe" / "consigne.md").write_text("Réponds en une phrase.\n", encoding="utf-8")
    refusee("equipe/ a des modifications non enregistrées")
    git("commit", "--quiet", "-am", "Consigne")
    (depot / "equipe" / "outils" / "nouveau.py").write_text("# pas encore enregistré\n", encoding="utf-8")
    refusee("equipe/ a des modifications non enregistrées")
    git("add", "equipe")
    git("commit", "--quiet", "-m", "Outil")
    refusee("des commits qui touchent equipe/ ne sont pas encore poussés")

    git("push", "--quiet")
    (depot / "traces").mkdir()
    (depot / "traces" / "vieille.json").write_text("{}\n", encoding="utf-8")  # traces/ ne compte pas
    assert evaluer.evaluer([batterie], officielle=True, racine=depot) == 0
    assert "| passe officielle" in capsys.readouterr().out
    _, trace = trace_unique(depot)
    assert trace["officielle"] is True and trace["modifie"] is False and trace["commit"]
    assert agent.questions == ["Combien ?"]

    deja = fichiers(depot / "traces" / "evaluations")
    assert evaluer.evaluer([batterie], racine=depot) == 0  # sans --officielle, rien n'est exigé
    assert nouvelle_trace(depot, deja)[1]["officielle"] is False


def test_bilan(depot, brancher_agent, faux_modele, monkeypatch, capsys):
    def instant(jour, heure):
        return datetime(2026, 11, jour, heure, 30, tzinfo=timezone.utc)

    for jour, entree, sortie, cout in ((17, 1000, 100, 0.001), (17, 500, 50, 0.0005), (18, 2000, 0, 0.002)):
        traces.ecrire_appel({"jetons": {"entree": entree, "sortie": sortie}, "cout_estime": cout}, depot,
                            instant(jour, 9))

    def avec_jetons(sortie):
        def repondre():
            modele.compter(modele.choisi(), 10_000, 1_000)  # comme le ferait le modèle du kit
            return sortie
        return repondre

    monkeypatch.setattr(traces, "maintenant", lambda: instant(18, 14))
    batterie = ecrire_batterie(depot / "equipe" / "questions" / "lot1.toml", [
        {"id": "q1", "texte": "Combien ?", "type": "nombre", "attendu": 12},
        {"id": "q2", "texte": "Quel poids ?", "type": "sans-reponse"},
    ])
    brancher_agent(FauxAgent({"Combien ?": avec_jetons(reponse(12)), "Quel poids ?": avec_jetons(ABSTENTION)}))
    assert evaluer.evaluer([batterie], racine=depot) == 0
    # Une batterie sans corrigé, que le faux agent ne connaît pas : trois questions en erreur.
    assert evaluer.evaluer([SANS_CORRIGE_EXEMPLE], racine=depot) == 1
    (depot / "traces" / "appels" / "2026-11-18" / "abime.json").write_text("{", encoding="utf-8")
    capsys.readouterr()
    avant = contenu(depot)

    assert bilan.bilan(depot) == 0

    lignes = capsys.readouterr().out.splitlines()
    assert lignes[0] == "Bilan des traces de ce dépôt"
    cout_evaluation = evaluer.en_dollars(2 * modele.cout(modele.choisi(), 10_000, 1_000))
    assert "2026-11-17 2 0 1 500 150 0,001500 $".split() in [ligne.split() for ligne in lignes]
    # Le 18 : un appel, cinq questions évaluées (deux, puis trois en erreur), et leurs jetons.
    jour = next(ligne for ligne in lignes if ligne.startswith("  2026-11-18"))
    assert jour.split()[1:5] == ["1", "5", "22", "000"]
    assert next(ligne for ligne in lignes if ligne.startswith("  total")).split()[1:3] == ["3", "5"]
    assert f"  2026-11-18 14:30 UTC  equipe/questions/lot1.toml, {modele.choisi()['identifiant']}" in lignes
    assert any(f"justesse 1/1 (100 %) | abstention 1/1 (100 %) | 2 questions, {cout_evaluation}" in ligne
               for ligne in lignes)
    assert any("kit/exemple/questions-sans-corrige.toml" in ligne and "table inventée" in ligne for ligne in lignes)
    assert any("justesse non notée | abstention non notée | 3 questions" in ligne for ligne in lignes)
    assert "1 fichier(s) de traces/ ne se lisent pas comme une trace : laissés de côté." in lignes
    assert lignes[-1].startswith("Traces non poussées : impossible à dire ici")
    assert faux_modele.appels == 0 and contenu(depot) == avant  # ni modèle, ni écriture

    monkeypatch.setattr(pousser, "traces_non_poussees", lambda racine: ["traces/evaluations/2026-11-18/x.json"])
    bilan.bilan(depot)
    assert capsys.readouterr().out.splitlines()[-1] == (
        "Traces non poussées : 1 trace ; pour les envoyer, uv run kit pousser"
    )


# --- Le reste ---------------------------------------------------------------------------


def test_exemple_sur_la_table_inventee():
    # Les trois fichiers d'exemple disent la même chose.
    complete = evaluer.lire(evaluer.BATTERIE_EXEMPLE)
    sans_corrige = evaluer.lire(SANS_CORRIGE_EXEMPLE)
    corrige = evaluer.lire(CORRIGE_EXEMPLE, corrige_seul=True)
    assert complete.questions == sans_corrige.questions and sans_corrige.corrige is None
    assert complete.corrige == corrige.corrige
    assert sorted(c["type"] for c in corrige.corrige.values()) == sorted(evaluer.TYPES)
    assert complete.exemple and sans_corrige.exemple

    # Et le corrigé est juste sur la table inventée, qu'agent_de_la_table lit par charger().
    with donnees.utiliser(donnees.EXEMPLE):
        assert len(donnees.charger()) == 12
        reponses = {q["id"]: agent_de_la_table()(q["texte"]) for q in complete.questions}
    assert donnees.en_cours == donnees.FICHIER
    verdicts = {ident: evaluer.juger({"reponse": r, "erreur": None}, complete.corrige[ident])
                for ident, r in reponses.items()}
    assert verdicts == {"q01": "juste", "q02": "juste", "q03": "abstention-fondee"}


def test_question_affichee_des_qu_elle_est_traitee(depot, brancher_agent, capsys):
    vu_pendant_la_seconde = []

    def bavard(sortie, regarder=False):
        def repondre():
            print("bavardage de l'agent")
            if regarder:
                vu_pendant_la_seconde.append(capsys.readouterr().out)
            return sortie
        return repondre

    batterie = ecrire_batterie(depot / "lot.toml", [{"id": "q1", "texte": "Un ?"}, {"id": "q2", "texte": "Deux ?"}])
    brancher_agent(FauxAgent({"Un ?": bavard(reponse(1)), "Deux ?": bavard(reponse(2), regarder=True)}))
    assert evaluer.evaluer([batterie], racine=depot) == 0
    (deja,) = vu_pendant_la_seconde
    assert "[1/2] q1 : Un ?" in deja and "réponse : 1 |" in deja and "[2/2] q2 : Deux ?" in deja
    assert "bavardage" not in deja + capsys.readouterr().out  # les étapes sont dans la trace

    assert evaluer.evaluer([batterie], detail=True, racine=depot) == 0
    assert "bavardage de l'agent" in vu_pendant_la_seconde[-1]  # avec --detail, ce que l'agent affiche passe


def test_sans_batterie(depot, capsys):
    (depot / "equipe" / "questions").mkdir()
    (depot / "equipe" / "questions" / ".gitkeep").write_text("", encoding="utf-8")
    assert evaluer.evaluer(racine=depot) == 1
    assert "Aucune batterie dans equipe/questions/" in capsys.readouterr().out
    assert evaluer.evaluer([depot / "equipe" / "questions" / "absente.toml"], racine=depot) == 1
    assert "le fichier est introuvable" in capsys.readouterr().out
    lot = ecrire_batterie(depot / "lot.toml", [{"id": "a", "texte": "b"}])
    assert evaluer.evaluer([lot], exemple=True, racine=depot) == 1
    assert "lance la commande sans --exemple" in capsys.readouterr().out
    assert not (depot / "traces").exists()


def test_ligne_de_commande(monkeypatch, capsys):
    vus = []
    monkeypatch.setattr(evaluer, "evaluer", lambda *a, **o: vus.append((a, o)) or 0)
    monkeypatch.setattr(evaluer, "noter", lambda *a, **o: vus.append((a, o)) or 0)

    assert cli.main(["evaluer"]) == 0
    assert cli.main(["evaluer", "b.toml", "--modele", "officiel", "--officielle", "--exemple", "--detail"]) == 0
    assert cli.main(["noter", "t.json", "--corrige", "c.toml", "--json"]) == 0
    assert vus == [
        (([],), {"exemple": False, "nom_modele": "developpement", "officielle": False, "detail": False}),
        ((["b.toml"],), {"exemple": True, "nom_modele": "officiel", "officielle": True, "detail": True}),
        (("t.json", "c.toml"), {"en_json": True}),
    ]
    capsys.readouterr()
    for appel, message_attendu in (
        (["evaluer", "--modele"], "L'option --modele attend une valeur"),
        (["evaluer", "a.toml", "b.toml"], "Argument en trop pour evaluer : b.toml"),
        (["evaluer", "--force"], "Option inconnue pour evaluer : --force"),
        (["noter", "t.json"], "Il manque la trace ou le corrigé"),
        (["bilan", "tout"], "Argument en trop pour bilan : tout"),
        (["controle", "hors-ligne"], "Argument en trop pour controle : hors-ligne"),
    ):
        assert cli.main(appel) == 1
        assert message_attendu in capsys.readouterr().out
    assert len(vus) == 3
    assert cli.main([]) == 0
    aide = capsys.readouterr().out
    assert all(verbe in aide for verbe in ("evaluer", "noter", "bilan", "--exemple", "--modele", "--officielle"))


def test_modele_inconnu(depot, capsys):
    assert evaluer.evaluer(exemple=True, nom_modele="le-plus-fort", racine=depot) == 1
    assert "Modèle inconnu : le-plus-fort. Ceux de kit/reglages.toml : developpement, officiel." in capsys.readouterr().out


def test_en_dollars_comme_le_modele():
    for montant in (0, 0.000123, 0.0099, 0.01, 0.5, 12.3456):
        assert evaluer.en_dollars(montant) == modele.en_dollars(montant)

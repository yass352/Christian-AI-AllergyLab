"""Le contrat de réponse : trois champs, validés, demandés au modèle par une consigne de format.

Les réponses de ces tests sont inventées : aucune ne porte sur le fichier réel.
"""

import pytest

from kit import cli, modele, question, reponse

from conftest import MOTEURS, lire_trace, message, reponse_finale

VALIDE = {"statut": "reponse", "valeur": 12, "justification": "La table inventée compte douze lignes."}


@pytest.mark.parametrize("sortie, attendu", [
    (VALIDE, VALIDE),
    ({"statut": "reponse", "valeur": 0.5, "justification": "Un nombre à virgule."}, None),
    ({"statut": "reponse", "valeur": "ALEX", "justification": "Un texte court. Deux phrases."}, None),
    ({"statut": "abstention", "valeur": None, "justification": "Je ne peux pas conclure."}, None),
    ('{"statut": "reponse", "valeur": 12, "justification": "La table inventée compte douze lignes."}', VALIDE),
    ({"statut": "abstention", "valeur": "", "justification": " Une. Deux ! Trois ? "},
     {"statut": "abstention", "valeur": None, "justification": "Une. Deux ! Trois ?"}),
])
def test_reponses_conformes(sortie, attendu):
    assert reponse.valider(sortie) == (attendu or sortie)


def test_nombre_de_numpy_ramene_a_python():
    numpy = pytest.importorskip("numpy")
    lue = reponse.valider({"statut": "reponse", "valeur": numpy.int64(12), "justification": "Douze."})
    assert lue["valeur"] == 12 and type(lue["valeur"]) is int


@pytest.mark.parametrize("sortie, raison", [
    ("12", "objet int"),
    ("douze lignes", "un texte, pas les trois champs"),
    (12, "objet int"),
    ({"statut": "reponse", "valeur": 12}, "le contrat demande statut, valeur, justification"),
    ({**VALIDE, "source": "x"}, "le contrat demande"),
    ({**VALIDE, "statut": "réponse"}, "le statut vaut"),
    ({**VALIDE, "statut": "abstention"}, "une abstention a une valeur vide"),
    ({**VALIDE, "valeur": None}, "nombre ou un texte non vide"),
    ({**VALIDE, "valeur": "  "}, "nombre ou un texte non vide"),
    ({**VALIDE, "valeur": True}, "nombre ou un texte non vide"),
    ({**VALIDE, "valeur": float("nan")}, "nombre ou un texte non vide"),
    ({**VALIDE, "valeur": [1, 2]}, "nombre ou un texte non vide"),
    ({**VALIDE, "justification": ""}, "justification est un texte non vide"),
    ({**VALIDE, "justification": "Un. Deux. Trois. Quatre."}, "compte 4 phrases"),
])
def test_reponses_illisibles(sortie, raison):
    with pytest.raises(reponse.ReponseIllisible, match=raison):
        reponse.valider(sortie)


def test_consigne_de_format():
    consigne = reponse.consigne("  Réponds en français.\n")
    assert consigne.startswith("Réponds en français.\n\n")
    assert consigne.endswith(reponse.FORMAT)
    for mot in ('"statut"', '"valeur"', '"justification"', '"reponse"', '"abstention"', "final_answer", "None"):
        assert mot in reponse.FORMAT


@pytest.mark.parametrize("moteur", MOTEURS)
def test_kit_agent_affiche_reponse_jetons_et_cout(moteur, faux_modele, cle_enregistree, depot, brancher, capsys):
    premier = message("<code>\nprint(12)\n</code>", entree=1000, sortie=40)
    if moteur == "boucle_maison":
        premier = message(outils=[("outil_absent", {})], entree=1000, sortie=40)
    faux_modele.programmer(premier, reponse_finale(moteur, VALIDE, entree=2000, sortie=60))
    brancher(moteur)

    assert question.poser("Combien de lignes compte la table inventée ?", depot) == 0

    sortie = capsys.readouterr().out
    assert "Réponse de l'agent\n  statut         reponse\n  valeur         12\n" in sortie
    assert "Jetons : 3 000 en entrée, 100 en sortie (claude-haiku-5-5)." in sortie
    reglage = modele.REGLAGES["modeles"]["developpement"]
    cout = (3000 * reglage["entree"] + 100 * reglage["sortie"]) / 1_000_000
    assert f"Coût estimé : {modele.en_dollars(cout)}." in sortie
    trace = lire_trace(depot)
    assert trace["reponse"] == VALIDE and trace["erreur"] is None
    assert trace["moteur"] == moteur and trace["modele"] == "claude-haiku-5-5"
    assert trace["jetons"] == {"entree": 3000, "sortie": 100}
    assert trace["cout_estime"] == pytest.approx(cout)
    assert len(trace["etapes"]) == 2 and trace["etapes"][0]["resultat"]


@pytest.mark.parametrize("moteur", MOTEURS)
def test_kit_agent_reponse_illisible(moteur, faux_modele, cle_enregistree, depot, brancher, capsys):
    faux_modele.programmer(reponse_finale(moteur, "12 lignes"))
    if moteur == "boucle_maison":
        faux_modele.reponses = [message("Il y a 12 lignes.")]  # du texte, sans appel de final_answer
    brancher(moteur)

    assert question.poser("Combien de lignes compte la table inventée ?", depot) == 1

    sortie = capsys.readouterr().out
    assert "Réponse illisible : l'agent a rendu un texte" in sortie
    assert "Que faire : la réponse finale passe par final_answer" in sortie
    assert "Jetons : 100 en entrée, 20 en sortie" in sortie
    trace = lire_trace(depot)
    assert "12 lignes" in trace["reponse"]  # la sortie brute est gardée, pour comprendre
    assert trace["erreur"].startswith("ReponseIllisible")


def test_sorties_tronquees(faux_modele, cle_enregistree, depot, brancher):
    longue = "x" * (modele.REGLAGES["agent"]["sortie_max"] + 500)
    faux_modele.programmer(
        message(f"<code>\nprint('{longue}')\n</code>"), reponse_finale("smolagents", VALIDE),
    )
    brancher("smolagents")
    assert question.poser("Combien ?", depot) == 0
    resultat = lire_trace(depot)["etapes"][0]["resultat"]
    assert resultat.endswith("caractères]") and len(resultat) < len(longue) + 100


def test_kit_agent_sans_question(capsys):
    assert cli.main(["agent"]) == 1
    assert 'uv run kit agent "' in capsys.readouterr().out


def test_boucle_maison_appelle_les_outils_de_l_equipe(faux_modele, cle_enregistree, depot, monkeypatch):
    from smolagents import tool

    from kit.boucle_maison import BoucleMaison

    @tool
    def doubler(nombre: int) -> int:
        """Double un nombre.

        Args:
            nombre: le nombre à doubler.
        """
        return 2 * nombre

    def repondre(question_posee):
        # Les mêmes paramètres que le CodeAgent de equipe/agent.py : seule la classe change.
        agent = BoucleMaison(
            model=modele.ModeleKit(), tools=[doubler], instructions=reponse.consigne("Réponds."),
            max_steps=8, max_print_outputs_length=2000, step_callbacks=[modele.noter_etape],
            additional_authorized_imports=["pandas"],
        )
        return agent.run(question_posee, additional_args={"tableau": object()})

    faux_modele.programmer(
        message(outils=[("doubler", {"nombre": 6})]),
        reponse_finale("boucle_maison", VALIDE),
    )
    monkeypatch.setattr(question, "charger_repondre", lambda racine: repondre)

    assert question.poser("Combien font deux fois six ?", depot) == 0

    assert faux_modele.appels == 2
    etapes = lire_trace(depot)["etapes"]
    assert etapes[0] == {"code": "doubler({'nombre': 6})", "resultat": "12"}
    assert etapes[1]["code"].startswith("final_answer(")

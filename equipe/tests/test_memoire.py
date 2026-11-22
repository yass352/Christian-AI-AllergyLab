"""La mémoire des réponses : une question déjà traitée par le même agent et le même modèle ne coûte aucun jeton."""

import pytest

from equipe import agent, memoire
from kit import modele, traces
from kit.reponse import valider

REPONSE = {"statut": "reponse", "valeur": 12, "justification": "Le tableau inventé compte douze lignes."}


@pytest.fixture
def depot(tmp_path):
    """Un dépôt minimal : equipe/ et son empreinte d'état."""
    (tmp_path / "equipe" / "outils").mkdir(parents=True)
    (tmp_path / "equipe" / "agent.py").write_text("def repondre(question):\n    return None\n", encoding="utf-8")
    (tmp_path / "equipe" / "consigne.md").write_text("Réponds.\n", encoding="utf-8")
    return tmp_path


def ecrire_trace(racine, question="Combien de lignes ?", reponse=REPONSE, modele_appele=None, erreur=None, etat=None):
    etat = etat or traces.empreinte_etat(traces.lire_etat(racine / "equipe"))
    champs = {
        "question": question, "reponse": reponse, "etat": etat, "erreur": erreur,
        "modele": modele_appele or modele.choisi()["identifiant"],
    }
    return traces.ecrire_appel(champs, racine)


def test_une_question_deja_traitee_est_reprise(depot):
    chemin = ecrire_trace(depot)
    reponse, trace = memoire.reponse_enregistree("  combien de LIGNES ?  ", depot)
    assert reponse == REPONSE
    assert trace == chemin.relative_to(depot).as_posix()


@pytest.mark.parametrize("ecart", [
    {"question": "Combien de colonnes ?"},
    {"modele_appele": "un-autre-modele"},
    {"erreur": "ErreurModele : saturé"},
    {"reponse": "un texte libre, hors contrat"},
    {"etat": "0000000000000000"},  # un autre état de l'agent
])
def test_rien_n_est_repris_sans_le_meme_agent_le_meme_modele_et_une_reponse_valide(depot, ecart):
    ecrire_trace(depot, **ecart)
    assert memoire.reponse_enregistree("Combien de lignes ?", depot) is None


def test_un_agent_modifie_ne_reprend_plus_ses_anciennes_reponses(depot):
    ecrire_trace(depot)
    (depot / "equipe" / "consigne.md").write_text("Une autre consigne.\n", encoding="utf-8")
    assert memoire.reponse_enregistree("Combien de lignes ?", depot) is None


def test_l_agent_repond_sans_appeler_le_modele(faux_modele, monkeypatch):
    faux = faux_modele()  # aucune réponse programmée : un appel au modèle échouerait
    monkeypatch.setattr(agent, "REUTILISER_LES_TRACES", True)
    monkeypatch.setattr(memoire, "reponse_enregistree", lambda question: (REPONSE, "traces/appels/x.json"))
    assert valider(agent.repondre("Combien de lignes ?")) == REPONSE
    assert faux.recus == []
    assert modele.journal["etapes"][-1]["code"].startswith("# Réponse reprise de traces/appels/x.json")

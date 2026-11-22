
import pytest

from equipe.securite import masquer_identifiants


def test_masquer_identifiant():
    texte = "Le patient PAT123 a 25 ans."
    resultat = masquer_identifiants(texte, ["PAT123"])

    assert resultat == "Le patient [IDENTIFIANT MASQU├ë] a 25 ans."


def test_ne_pas_masquer_une_partie_d_un_identifiant():
    texte = "Patient 1234 et patient 123"

    resultat = masquer_identifiants(texte, ["123"])

    assert resultat == "Patient 1234 et patient [IDENTIFIANT MASQU├ë]"


def test_masquer_plusieurs_identifiants():
    texte = "PAT123 et PAT456 sont concern├®s."

    resultat = masquer_identifiants(texte, ["PAT123", "PAT456"])

    assert resultat == "[IDENTIFIANT MASQU├ë] et [IDENTIFIANT MASQU├ë] sont concern├®s."


def test_identifiant_vide():
    texte = "Aucune donn├®e ├á masquer."

    resultat = masquer_identifiants(texte, [""])

    assert resultat == texte


def test_texte_invalide():
    with pytest.raises(TypeError):
        masquer_identifiants(123, ["PAT123"])


def test_liste_identifiants_invalide():
    with pytest.raises(TypeError):
        masquer_identifiants("Patient PAT123", "PAT123")

"""Le tokenizer de litellm se lit dans sa copie, même aux fins de ligne CRLF, sans rien télécharger.

litellm compte les jetons avec tiktoken, et lui fait lire la copie du
tokenizer qu'il embarque. Dans la roue Windows de litellm, cette copie a des
fins de ligne CRLF : sans le correctif de kit/modele.py, tiktoken la
rejetterait et irait la télécharger. Ce test fabrique une telle copie, sur les
trois systèmes, et vérifie que tiktoken la lit sans toucher au réseau.
"""

import hashlib
import socket
from pathlib import Path

import litellm
import tiktoken.load

from kit import modele  # noqa: F401  # l'importer installe le correctif dans tiktoken

from conftest import refuser_le_reseau

# L'adresse et l'empreinte SHA-256 que tiktoken donne au tokenizer que litellm
# charge, cl100k_base (tiktoken_ext/openai_public.py).
ADRESSE = "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"
EMPREINTE = "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"


def test_copie_crlf_sans_telechargement(tmp_path, monkeypatch):
    # tiktoken nomme sa copie par l'empreinte SHA-1 de l'adresse.
    nom = hashlib.sha1(ADRESSE.encode(), usedforsecurity=False).hexdigest()
    installee = Path(litellm.__file__).parent / "litellm_core_utils" / "tokenizers" / nom
    # Le contenu attendu : la copie installée, en fins de ligne LF, quel que soit le système.
    attendu = installee.read_bytes().replace(b"\r\n", b"\n")
    assert tiktoken.load.check_hash(attendu, EMPREINTE)

    # La même en CRLF, comme dans la roue Windows : son empreinte n'est plus la bonne.
    crlf = attendu.replace(b"\n", b"\r\n")
    assert not tiktoken.load.check_hash(crlf, EMPREINTE)
    (tmp_path / nom).write_bytes(crlf)
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(tmp_path))

    # Aucun téléchargement : tiktoken télécharge par read_file, et rien ne sort sur le réseau.
    telechargements = []

    def telecharger(adresse):
        telechargements.append(adresse)
        raise RuntimeError(f"tiktoken a tenté de télécharger {adresse}.")

    monkeypatch.setattr(tiktoken.load, "read_file", telecharger)
    monkeypatch.setattr(socket.socket, "connect", refuser_le_reseau)

    # La fonction même que tiktoken appelle pour lire un tokenizer.
    contenu = tiktoken.load.read_file_cached(ADRESSE, EMPREINTE)

    assert contenu == attendu
    assert telechargements == []
    # tiktoken supprime une copie qu'il rejette : celle-ci est restée telle quelle.
    assert (tmp_path / nom).read_bytes() == crlf

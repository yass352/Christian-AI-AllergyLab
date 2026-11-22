"""pousser : les traces partent en une commande, et rien d'autre ne bouge.

Ni réseau ni GitHub : un dépôt git local, créé dans un dossier temporaire,
joue le dépôt de l'équipe, et deux clones jouent deux portables. Chaque test
a sa propre configuration git, qui ignore celle de la machine et celle de
l'utilisateur. Aucun test ne lance pousser sur le dépôt du kit lui-même.
"""

import ast
import secrets
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from kit import cli, controle, pousser

AGENT = "".join(f"# ligne {numero}\n" for numero in range(1, 7))
CONFIGURATION = "[user]\n\tname = kit\n\temail = kit\n[init]\n\tdefaultBranch = main\n[commit]\n\tgpgsign = false\n"
RIEN_A_ENVOYER = "RÉUSSITE : rien à envoyer, le dépôt de l'équipe a déjà toutes tes traces."


# --- Outils -------------------------------------------------------------------


def git(dossier, *arguments):
    """Un geste git fait à la main, par le test ou par un coéquipier : il doit réussir."""
    resultat = subprocess.run(
        ["git", *arguments], cwd=dossier, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr
    return resultat.stdout


def ecrire(chemin, texte):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8", newline="\n")
    return chemin


def ecrire_trace(clone):
    """Une trace d'appel, nommée comme le kit les nomme."""
    nom = f"20261117T100000Z-{secrets.token_hex(4)}.json"
    return ecrire(clone / "traces" / "appels" / "2026-11-17" / nom, '{"format": 1}\n')


def ecrire_etat(clone):
    """Un état du travail. Deux clones au même travail écrivent le même."""
    dossier = clone / "traces" / "etats" / "0123456789abcdef"
    ecrire(dossier / "agent.py", AGENT)
    ecrire(dossier / "consigne.md", "Réponds.\n")


def remplacer_ligne(fichier, numero, texte):
    lignes = fichier.read_text(encoding="utf-8").splitlines(keepends=True)
    lignes[numero - 1] = texte + "\n"
    ecrire(fichier, "".join(lignes))


def enregistrer_a_la_main(clone, fichier, message):
    git(clone, "add", fichier)
    git(clone, "commit", "--quiet", "-m", message)


def relatif(clone, chemin):
    return chemin.relative_to(clone).as_posix()


def contenu(clone):
    """Les octets de chaque fichier du dossier, hors .git."""
    return {
        relatif(clone, fichier): fichier.read_bytes()
        for fichier in clone.rglob("*")
        if fichier.is_file() and ".git" not in fichier.relative_to(clone).parts
    }


def tete(dossier, reference="HEAD"):
    return git(dossier, "rev-parse", reference).strip()


def sur_le_distant(equipe):
    """Les fichiers de la branche main du dépôt de l'équipe."""
    return set(git(equipe.distant, "ls-tree", "-r", "--name-only", "main").splitlines())


def pousse_un_coequipier(clone, fichier="equipe/outils/outil.py"):
    """Un coéquipier enregistre et pousse un fichier, à la main."""
    git(clone, "pull", "--quiet", "--rebase")
    ecrire(clone / fichier, f"# {secrets.token_hex(4)}\n")
    enregistrer_a_la_main(clone, fichier, "Travail d'un coéquipier")
    git(clone, "push", "--quiet")


def derniere_ligne(sortie):
    return sortie.strip().splitlines()[-1]


@pytest.fixture
def equipe(tmp_path, monkeypatch):
    """Le dépôt de l'équipe, et deux clones à jour : a, sous un chemin à espaces et accents, et b."""
    if shutil.which("git") is None:
        pytest.skip("git absent de cette machine")
    configuration = ecrire(tmp_path / "gitconfig", CONFIGURATION)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(configuration))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    for variable in (
        "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "EMAIL",
    ):
        monkeypatch.delenv(variable, raising=False)

    distant = tmp_path / "distant.git"
    git(tmp_path, "init", "--quiet", "--bare", str(distant))
    amorce = tmp_path / "amorce"
    ecrire(amorce / "equipe.toml", 'equipe = "equipe-3"\n')
    ecrire(amorce / "equipe" / "agent.py", AGENT)
    ecrire(amorce / "equipe" / "consigne.md", "Réponds.\n")
    git(amorce, "init", "--quiet")
    enregistrer_a_la_main(amorce, "equipe.toml", "Départ")
    enregistrer_a_la_main(amorce, "equipe", "Départ de l'équipe")
    git(amorce, "push", "--quiet", str(distant), "main")

    a, b = tmp_path / "Dossier de l'élève" / "a", tmp_path / "b"
    a.parent.mkdir()
    for clone in (a, b):
        git(tmp_path, "clone", "--quiet", str(distant), str(clone))
    return SimpleNamespace(distant=distant, a=a, b=b)


# --- Les cas nommés par le prompt ------------------------------------------------


def test_pousser_envoie_les_traces(equipe, capsys):
    a = equipe.a
    traces = {relatif(a, ecrire_trace(a)) for _ in range(2)}
    ecrire_etat(a)

    assert pousser.pousser(a) == 0

    sortie = capsys.readouterr().out
    assert "  OK     traces enregistrées : 2 traces et 1 état du travail" in sortie
    assert derniere_ligne(sortie) == "RÉUSSITE : le dépôt de l'équipe a reçu 2 traces et 1 état du travail."
    distant = sur_le_distant(equipe)
    assert traces <= distant
    assert "traces/etats/0123456789abcdef/agent.py" in distant
    assert git(a, "status", "--porcelain") == ""
    assert tete(a) == tete(equipe.distant, "main")
    envoyes = git(a, "show", "--name-only", "--format=", "HEAD").split()
    assert envoyes and all(nom.startswith("traces/") for nom in envoyes)


def test_deux_clones_sans_geste_manuel(equipe, capsys):
    a, b = equipe.a, equipe.b
    trace_a, trace_b = relatif(a, ecrire_trace(a)), relatif(b, ecrire_trace(b))
    ecrire_etat(a)
    ecrire_etat(b)  # même travail, même état : le même fichier part des deux côtés

    assert pousser.pousser(a) == 0
    assert pousser.pousser(b) == 0  # b n'a pas récupéré le push de a : pousser s'en charge
    assert pousser.pousser(a) == 0  # a récupère la trace de b, et n'a plus rien à envoyer

    assert derniere_ligne(capsys.readouterr().out) == RIEN_A_ENVOYER
    assert {trace_a, trace_b} <= sur_le_distant(equipe)
    assert (a / trace_b).is_file()
    for clone in (a, b):
        assert git(clone, "status", "--porcelain") == ""
        assert tete(clone) == tete(equipe.distant, "main")


def test_fichier_modifie_reste_intact(equipe, capsys):
    a = equipe.a
    pousse_un_coequipier(equipe.b)  # a devra récupérer avant de pousser, en mettant son travail de côté
    remplacer_ligne(a / "equipe" / "agent.py", 3, "# modifié, pas encore enregistré")
    ecrire(a / "equipe" / "outils" / "nouveau.py", "# indexé, pas encore enregistré\n")
    git(a, "add", "equipe/outils/nouveau.py")  # déjà indexé : il ne doit pas partir pour autant
    trace = relatif(a, ecrire_trace(a))
    avant = contenu(a)

    assert pousser.pousser(a) == 0, capsys.readouterr().out

    apres = contenu(a)
    for nom in ("equipe/agent.py", "equipe/outils/nouveau.py"):
        assert apres[nom] == avant[nom]
    assert set(git(a, "diff", "--name-only", "HEAD").split()) == {"equipe/agent.py", "equipe/outils/nouveau.py"}
    assert git(a, "stash", "list") == ""
    distant = sur_le_distant(equipe)
    assert trace in distant and "equipe/outils/nouveau.py" not in distant
    assert git(equipe.distant, "show", "main:equipe/agent.py") == AGENT


def test_conflit_remet_en_etat(equipe, capsys):
    """Un commit de a et un commit de b touchent la même ligne : le rebase s'arrête, pousser l'annule."""
    a, b = equipe.a, equipe.b
    remplacer_ligne(b / "equipe" / "agent.py", 2, "# version de b")
    enregistrer_a_la_main(b, "equipe/agent.py", "Version de b")
    git(b, "push", "--quiet")
    remplacer_ligne(a / "equipe" / "agent.py", 2, "# version de a")
    enregistrer_a_la_main(a, "equipe/agent.py", "Version de a")  # enregistrée, pas encore poussée
    remplacer_ligne(a / "equipe" / "consigne.md", 1, "Réponds en une phrase.")  # ni enregistrée ni poussée
    ecrire_trace(a)
    avant, tete_avant, distant_avant = contenu(a), tete(a), tete(equipe.distant, "main")

    assert pousser.pousser(a) == 1

    assert derniere_ligne(capsys.readouterr().out) == (
        "ÉCHEC : un coéquipier a modifié le même fichier que toi (equipe/agent.py) : "
        "ton dossier est resté tel quel, appelle l'animateur."
    )
    assert contenu(a) == avant
    assert not pousser.operation_en_cours(pousser.dossier_git(a))
    assert git(a, "status", "--porcelain").splitlines() == [" M equipe/consigne.md"]
    assert git(a, "stash", "list") == ""
    assert tete(equipe.distant, "main") == distant_avant
    # Reste le commit des traces, fait avant la récupération : il partira au prochain envoi.
    assert tete(a, "HEAD~1") == tete_avant


def test_conflit_sur_un_fichier_non_enregistre(equipe, capsys):
    """b a poussé agent.py, que a modifie sans l'enregistrer : pousser s'arrête avant de rien toucher.

    Même sur une autre ligne : récupérer changerait le fichier, qui doit rester tel quel.
    """
    a, b = equipe.a, equipe.b
    remplacer_ligne(b / "equipe" / "agent.py", 2, "# version de b")
    enregistrer_a_la_main(b, "equipe/agent.py", "Version de b")
    git(b, "push", "--quiet")
    remplacer_ligne(a / "equipe" / "agent.py", 5, "# version de a, plus bas")
    trace = relatif(a, ecrire_trace(a))
    avant, tete_avant = contenu(a), tete(a)

    assert pousser.pousser(a) == 1

    assert "ÉCHEC : un coéquipier a modifié le même fichier que toi (equipe/agent.py)" in capsys.readouterr().out
    assert contenu(a) == avant
    assert tete(a) == tete_avant  # rien d'enregistré, rien de récupéré
    etat = set(git(a, "status", "--porcelain", "--untracked-files=all").splitlines())
    assert etat == {" M equipe/agent.py", f"?? {trace}"}


def test_refuse_un_clone_non_rattache(equipe, capsys):
    a = equipe.a
    ecrire(a / "equipe.toml", 'equipe = "accueil"\n')
    enregistrer_a_la_main(a, "equipe.toml", "Comme un clone du dépôt du kit")
    trace = relatif(a, ecrire_trace(a))
    tete_avant = tete(a)

    assert pousser.pousser(a) == 1

    sortie = capsys.readouterr().out
    assert derniere_ligne(sortie) == f"ÉCHEC : {pousser.NON_RATTACHE}"
    assert "« accueil »" in sortie and "animateur" in sortie
    assert tete(a) == tete_avant
    assert git(a, "status", "--porcelain", "--untracked-files=all").splitlines() == [f"?? {trace}"]


def test_sans_identite_git(equipe, tmp_path, monkeypatch, capsys):
    vide = ecrire(tmp_path / "gitconfig-vide", "")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(vide))
    ecrire_trace(equipe.a)
    tete_avant = tete(equipe.a)

    assert pousser.pousser(equipe.a) == 1

    sortie = capsys.readouterr().out
    assert "ÉCHEC : git ne sait pas qui signe les commits" in sortie
    assert '    git config --global user.name "' in sortie
    assert '    git config --global user.email "' in sortie
    assert vide.read_text(encoding="utf-8") == ""  # les commandes sont données, pas lancées
    assert tete(equipe.a) == tete_avant


def test_sans_git(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    archive = tmp_path / "archive"
    ecrire(archive / "equipe.toml", 'equipe = "equipe-3"\n')
    ecrire_trace(archive)

    if shutil.which("git"):
        assert pousser.pousser(archive) == 1  # un dossier qui n'est pas un dépôt git
        assert derniere_ligne(capsys.readouterr().out) == f"ÉCHEC : {pousser.PAS_UN_DEPOT}"
        assert pousser.traces_non_poussees(archive) is None

    monkeypatch.setenv("PATH", "")  # git introuvable
    assert pousser.pousser(archive) == 1
    assert derniere_ligne(capsys.readouterr().out) == f"ÉCHEC : {pousser.GIT_ABSENT}"
    assert pousser.traces_non_poussees(archive) is None
    assert not (archive / ".git").exists()


def test_rien_a_pousser(equipe, capsys):
    (equipe.a / "traces" / "appels").mkdir(parents=True)  # un dossier de traces encore vide
    tete_avant = tete(equipe.a)

    assert pousser.pousser(equipe.a) == 0

    sortie = capsys.readouterr().out
    assert "  OK     aucune trace nouvelle à enregistrer" in sortie
    assert derniere_ligne(sortie) == RIEN_A_ENVOYER
    assert tete(equipe.a) == tete_avant == tete(equipe.distant, "main")


# --- Push refusé, connexion, sortie de git -------------------------------------


def git_avec_un_coequipier(monkeypatch, equipe, combien):
    """Avant chacun des combien premiers push de pousser, b pousse un fichier. Rend la liste des push tentés."""
    vrai_git, push = pousser.git, []

    def git_espionne(racine, *arguments, **options):
        if arguments[:1] == ("push",):
            push.append(racine)
            if len(push) <= combien:
                pousse_un_coequipier(equipe.b, f"equipe/outils/outil_{len(push)}.py")
        return vrai_git(racine, *arguments, **options)

    monkeypatch.setattr(pousser, "git", git_espionne)
    return push


def test_un_coequipier_pousse_entre_temps(equipe, monkeypatch, capsys):
    push = git_avec_un_coequipier(monkeypatch, equipe, combien=1)
    trace = relatif(equipe.a, ecrire_trace(equipe.a))

    assert pousser.pousser(equipe.a) == 0

    sortie = capsys.readouterr().out
    assert "  --     un coéquipier a poussé entre-temps : nouvel essai (2 sur 3)" in sortie
    assert derniere_ligne(sortie) == "RÉUSSITE : le dépôt de l'équipe a reçu 1 trace."
    assert len(push) == 2
    assert trace in sur_le_distant(equipe)
    assert (equipe.a / "equipe" / "outils" / "outil_1.py").is_file()


def test_trois_essais_au_plus(equipe, monkeypatch, capsys):
    push = git_avec_un_coequipier(monkeypatch, equipe, combien=99)
    trace = relatif(equipe.a, ecrire_trace(equipe.a))

    assert pousser.pousser(equipe.a) == 1

    assert derniere_ligne(capsys.readouterr().out) == (
        "ÉCHEC : le dépôt de l'équipe a changé pendant chacun des 3 essais. Tes traces sont enregistrées : "
        "relance uv run kit pousser dans une minute."
    )
    assert len(push) == 3
    assert trace not in sur_le_distant(equipe)
    assert trace in git(equipe.a, "ls-files")  # enregistrée, elle partira au prochain envoi


def test_connexion_refusee(equipe, tmp_path, capsys):
    a = equipe.a
    git(a, "remote", "set-url", "origin", str(tmp_path / "introuvable.git"))
    trace = relatif(a, ecrire_trace(a))
    tete_avant = tete(a)

    assert pousser.pousser(a) == 1

    sortie = capsys.readouterr().out
    assert derniere_ligne(sortie) == f"ÉCHEC : {pousser.CONNEXION_REFUSEE}"
    assert "terminal intégré de VS Code" in sortie
    assert tete(a) == tete_avant
    assert git(a, "status", "--porcelain", "--untracked-files=all").splitlines() == [f"?? {trace}"]


def test_sortie_de_git_seulement_avec_detail(equipe, capsys):
    ecrire_trace(equipe.a)
    assert pousser.pousser(equipe.a) == 0
    sans = capsys.readouterr().out
    assert "$ git" not in sans and "->" not in sans

    ecrire_trace(equipe.a)
    assert pousser.pousser(equipe.a, detail=True) == 0
    avec = capsys.readouterr().out
    assert "  $ git push" in avec and "main -> main" in avec


# --- Le contrôle, la ligne de commande, les gestes interdits -----------------------


def test_controle_signale_les_traces_non_poussees(equipe, capsys):
    a = equipe.a
    assert pousser.traces_non_poussees(a) == []
    ecrire_trace(a)
    ecrire_etat(a)

    controle.signaler_traces_non_poussees(a)
    assert capsys.readouterr().out == (
        "  INFO   traces non poussées : 1 trace et 1 état du travail ; pour les envoyer, uv run kit pousser\n"
    )

    assert pousser.pousser(a) == 0
    capsys.readouterr()
    assert pousser.traces_non_poussees(a) == []
    controle.signaler_traces_non_poussees(a)
    assert capsys.readouterr().out == ""


def test_traces_non_poussees_ne_font_pas_echouer_le_controle(monkeypatch, capsys):
    monkeypatch.setattr(pousser, "traces_non_poussees", lambda racine: ["traces/appels/2026-11-17/x.json"])
    assert controle.controler(hors_ligne=True) == 0
    sortie = capsys.readouterr().out
    assert "  INFO   traces non poussées : 1 trace ; pour les envoyer, uv run kit pousser" in sortie
    assert derniere_ligne(sortie) == "RÉUSSITE"


def test_decompte():
    assert pousser.decompte([]) == ""
    assert pousser.decompte(["traces/.gitkeep"]) == ""
    assert pousser.decompte(["traces/appels/j/1.json"]) == "1 trace"
    assert pousser.decompte(["traces/etats/e/agent.py", "traces/etats/e/outils/x.py"]) == "1 état du travail"
    chemins = ["traces/appels/j/1.json", "traces/appels/j/2.json", "traces/etats/e/agent.py", "traces/etats/f/agent.py"]
    assert pousser.decompte(chemins) == "2 traces et 2 états du travail"


def test_commande_pousser(monkeypatch, capsys):
    """La ligne de commande appelle pousser, et lui passe --detail. Le vrai pousser ne tourne pas ici."""
    vus = []

    def faux_pousser(detail=False):
        vus.append(detail)
        return 0

    monkeypatch.setattr(pousser, "pousser", faux_pousser)
    assert cli.main(["pousser"]) == 0
    assert cli.main(["pousser", "--detail"]) == 0
    assert cli.main(["pousser", "--force"]) == 1
    assert vus == [False, True]
    assert cli.main([]) == 0
    assert "pousser" in capsys.readouterr().out


def test_aucun_geste_destructeur():
    """Ni push forcé, ni reset, ni suppression ; add et commit ne portent que sur traces/."""
    interdits = {
        "--force", "-f", "--force-with-lease", "--mirror", "--delete", "-d", "-D", "reset", "rm", "clean",
        "drop", "clear", "--hard", "checkout", "restore", "-a", "--all", "-A", ".",
    }
    arbre = ast.parse(Path(pousser.__file__).read_text(encoding="utf-8"))
    appels = [n for n in ast.walk(arbre) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "git"]
    assert len(appels) > 10
    for appel in appels:
        mots = [a.value for a in appel.args[1:] if isinstance(a, ast.Constant)]
        assert not set(mots) & interdits, f"ligne {appel.lineno} : {mots}"
        if mots[:1] in (["add"], ["commit"]):
            assert mots[-2:] == ["--", "traces"], f"ligne {appel.lineno} : {mots}"

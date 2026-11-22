#!/usr/bin/env python3
"""
AllergyLab - Est-ce que ma machine peut faire tourner un modele en local ?

Usage :  python3 verifier-ma-machine.py

Aucune dependance a installer. Fonctionne sur macOS, Windows et Linux.
Le script ne lit que les caracteristiques de la machine, n'envoie rien
et n'ecrit aucun fichier.
"""

import platform
import shutil
import subprocess
import sys


def go(cmd):
    """Lance une commande et renvoie sa sortie, ou None si elle echoue."""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def ram_go():
    """Memoire vive totale, en Go."""
    s = platform.system()
    if s == "Darwin":
        v = go(["sysctl", "-n", "hw.memsize"])
        return int(v) / 1024**3 if v else None
    if s == "Linux":
        try:
            with open("/proc/meminfo") as f:
                for ligne in f:
                    if ligne.startswith("MemTotal:"):
                        return int(ligne.split()[1]) / 1024**2
        except Exception:
            return None
    if s == "Windows":
        v = go(["powershell", "-NoProfile", "-Command",
                "(Get-CIMInstance Win32_ComputerSystem).TotalPhysicalMemory"])
        if v and v.isdigit():
            return int(v) / 1024**3
        v = go(["wmic", "computersystem", "get", "TotalPhysicalMemory"])
        if v:
            for mot in v.split():
                if mot.isdigit():
                    return int(mot) / 1024**3
    return None


def vram_nvidia_go():
    """VRAM de la carte NVIDIA la plus grosse, en Go, ou None."""
    if not shutil.which("nvidia-smi"):
        return None
    v = go(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"])
    if not v:
        return None
    tailles = [int(x) for x in v.split("\n") if x.strip().isdigit()]
    return max(tailles) / 1024 if tailles else None


def puce_apple():
    """Nom de la puce sur un Mac Apple Silicon, ou None."""
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return None
    return go(["sysctl", "-n", "machdep.cpu.brand_string"]) or "Apple Silicon"


def verdict():
    systeme = platform.system()
    ram = ram_go()
    vram = vram_nvidia_go()
    apple = puce_apple()

    lignes = []
    lignes.append(f"Systeme        : {systeme} {platform.release()}")
    lignes.append(f"Processeur     : {apple or platform.processor() or platform.machine()}")
    lignes.append(f"Memoire vive   : {ram:.0f} Go" if ram else "Memoire vive   : inconnue")
    if vram:
        lignes.append(f"GPU NVIDIA     : {vram:.0f} Go de VRAM")
    elif systeme != "Darwin":
        lignes.append("GPU NVIDIA     : aucun detecte")

    # Apple Silicon : la memoire est unifiee, c'est elle qui commande.
    if apple and ram:
        if ram >= 32:
            return lignes, "CONFORTABLE", (
                "Tu peux viser un modele de 14B en quantification 4 bits, et "
                "meme tenter plus gros. L'option locale est une vraie piste pour ton equipe."
            )
        if ram >= 16:
            return lignes, "JOUABLE", (
                "Un modele de 7B a 8B en quantification 4 bits tiendra, avec une vitesse "
                "correcte. Attention, l'appel d'outils reste fragile a cette taille : "
                "c'est justement ce qu'on te demandera de mesurer."
            )
        return lignes, "LIMITE", (
            "8 Go de memoire unifiee ne laissent la place qu'a un modele de 3B a 4B. "
            "Ca demarre, mais la fiabilite sera faible. A reserver a une comparaison, "
            "pas au projet principal."
        )

    # Mac Intel : pas d'acceleration exploitable.
    if systeme == "Darwin":
        return lignes, "NON", (
            "Les Mac a processeur Intel n'ont pas de memoire unifiee ni d'acceleration "
            "Metal utilisable pour un LLM. L'inference tournerait sur le processeur seul, "
            "trop lentement pour une boucle d'agent. Prends l'option par defaut."
        )

    # Windows et Linux : c'est la VRAM qui commande.
    if vram:
        if vram >= 16:
            return lignes, "CONFORTABLE", (
                "Ta carte encaisse un modele de 14B en quantification 4 bits. "
                "L'option locale est une vraie piste pour ton equipe."
            )
        if vram >= 8:
            return lignes, "JOUABLE", (
                "Un modele de 7B a 8B en quantification 4 bits tiendra dans ta VRAM. "
                "Attention, l'appel d'outils reste fragile a cette taille : c'est "
                "justement ce qu'on te demandera de mesurer."
            )
        return lignes, "LIMITE", (
            "Moins de 8 Go de VRAM limitent a un modele de 3B a 4B. Ca demarre, mais "
            "la fiabilite sera faible. A reserver a une comparaison, pas au projet principal."
        )

    return lignes, "NON", (
        "Aucun GPU exploitable detecte. Sans carte graphique dediee, l'inference "
        "tourne sur le processeur seul, trop lentement pour une boucle d'agent. "
        "Prends l'option par defaut, tu ne perds rien."
    )


def main():
    try:
        lignes, note, commentaire = verdict()
    except Exception as e:  # on ne laisse jamais un etudiant devant une trace
        print("Le script n'a pas reussi a lire ta configuration.")
        print(f"Detail : {e}")
        print("Signale-le sur Discord, on regardera ensemble.")
        return 1

    largeur = 72
    print()
    print("=" * largeur)
    print("  AllergyLab - verification de ta machine".upper())
    print("=" * largeur)
    for l in lignes:
        print("  " + l)
    print("-" * largeur)
    print(f"  VERDICT : {note}")
    print("-" * largeur)
    for mot in decouper(commentaire, largeur - 4):
        print("  " + mot)
    print("=" * largeur)
    print()
    print("  Rappel : ce verdict ne conditionne que l'option locale, facultative.")
    print("  L'option par defaut fonctionne sur n'importe quelle machine.")
    print()
    return 0


def decouper(texte, largeur):
    """Petit retour a la ligne maison, pour ne rien importer."""
    mots, ligne, sortie = texte.split(), "", []
    for m in mots:
        if len(ligne) + len(m) + 1 > largeur:
            sortie.append(ligne)
            ligne = m
        else:
            ligne = f"{ligne} {m}".strip()
    if ligne:
        sortie.append(ligne)
    return sortie


if __name__ == "__main__":
    sys.exit(main())

# SPEC : kit de démarrage AllergyLab

Semaine du 16 au 20 novembre 2026. Version 3, du 16 novembre 2026. Remplace celle du 13 novembre.

**Marqueurs.** [Décision] et [Fait] renvoient au dossier de passation, version du 13 novembre. [Hypothèse] marque ce qui reste à confirmer. Tout le reste est une proposition du chef de projet, qui devient décision quand Adrien valide cette spec.

**Publiable.** Cette spec vit à la racine du dépôt du kit, que les étudiants liront. Elle ne nomme aucun piège du fichier, ne donne aucune réponse et ne décrit pas le déroulé de la semaine.

**Vocabulaire.** Le kit est un **harnais** : tout ce qui entoure le modèle et le rend utilisable, c'est-à-dire la boucle, les outils, la consigne, les garde-fous, les traces. C'est le mot que les étudiants retrouveront dans les offres. La partie qui note l'agent s'appelle toujours « harnais d'évaluation », en toutes lettres.

**Ce qui change depuis le 11 novembre.**

- Le fichier de données entre dans le dépôt [Décision]. Plus aucun téléchargement de données à l'installation.
- L'agent minimal reste un `CodeAgent`, livré ouvert ; l'équipe décide ensuite de fermer son accès au tableau [Décision] (§ 5.3).
- Les dépôts d'équipe sont privés, dans l'organisation `sprint-dojo` [Décision] (§ 8).
- Le `.devcontainer` et le générateur du dictionnaire passent au lot 2 [Décision]. Un lot 3 porte deux options pour le mercredi (§ 10).
- La clé d'API se range hors du dépôt (§ 4) [Décision].
- De cinq à sept équipes, et trois cagnottes par équipe au lieu d'une enveloppe unique [Décision] (§§ 7.2 et 8).

**Ce qui change depuis le 13 novembre.**

- Une commande `uv run kit pousser` envoie les traces vers le dépôt de l'équipe (§§ 4 et 7.4).
- Le harnais d'évaluation mesure aussi la frugalité, et la notation peut se faire après coup, par une commande à part (§ 5.4).
- Les lots 2 et suivants ne touchent ni à `equipe/`, ni à `equipe.toml`, ni à `README.md`, ni à `JOURNAL.md` : ces fichiers appartiennent aux équipes (§ 8).
- Le calendrier des lots est revu (§ 10).

## 1. Le scénario qui juge

Lundi 16 novembre, 9h30. Vingt étudiants de deuxième année, portable personnel sous macOS, Windows ou Linux, droits d'administrateur non garantis, bases de Python et rien de plus. À 10h30 au plus tard, chacun a le kit qui tourne et a vu l'agent minimal répondre à une question. Au-delà d'une heure, la semaine est abîmée.

Chaque exigence de cette spec sert ce scénario ou la collecte des traces (§ 7). Ce qui ne sert ni l'un ni l'autre n'entre pas dans le kit.

| Heure | Étape | Commande |
|---|---|---|
| 9h30 | Cloner le dépôt public, sans compte ni mot de passe | `git clone …` |
| 9h40 | Installer | `uv run kit installer` |
| 9h50 | Contrôler | `uv run kit controle` |
| 9h55 | Poser une question à l'agent minimal | `uv run kit agent "…"` |
| 10h05 | Réserve de vingt-cinq minutes pour les machines qui résistent (§ 3) | |

## 2. Prérequis et machine vierge

Deux outils, installés par chaque étudiant avant lundi : **git** et **uv**. Ils en reçoivent la marche à suivre par mail.

Pourquoi uv. Il s'installe dans le dossier de l'utilisateur, de la même façon sur les trois systèmes, et il télécharge lui-même la bonne version de Python. Personne n'installe Python à la main, personne n'active d'environnement virtuel : toutes les commandes passent par `uv run`. Un animateur seul n'a qu'une procédure à dépanner.

« Machine vierge », dans toute cette spec : un système avec git et uv, sans Python, sans cache uv, sans aucun fichier du kit.

- Python 3.12, version figée dans le dépôt. [Hypothèse] compatible avec smolagents 1.26.0 ; `tester-la-stack.py` tranche.
- Dépendances figées par un fichier de verrouillage versionné : smolagents 1.26.0 [Décision], pandas, pytest, et ce que `tester-la-stack.py` exige pour parler à Claude. Rien d'autre à la livraison. Une équipe ajoute une bibliothèque par `uv add`, une personne à la fois.
- Consigne de clonage : dans le dossier personnel, hors des dossiers synchronisés (OneDrive, iCloud).

## 3. Quand une machine résiste

Lundi, deux replis.

1. **Étudiant arrivé sans les prérequis.** uv s'installe en une commande. Sans git, il télécharge l'archive ZIP du dépôt. Le kit doit donc tourner depuis un dossier qui n'est pas un dépôt git ; les traces notent alors l'absence de commit.
2. **Machine qui échoue encore à 10h05.** Binôme jusqu'à la pause, et on répare à ce moment-là.

À partir du lot 2, un troisième repli : un fichier `.devcontainer` ouvre le kit dans le navigateur, sur une machine distante fournie par GitHub Codespaces, avec le même verrouillage et les mêmes commandes. Le quota gratuit d'un compte personnel couvre la semaine. C'est la même chaîne technique, sous Linux [Décision 3], et c'est aussi la seule isolation disponible pour qui ne veut pas exécuter le code d'un modèle sur sa machine (§ 5.3).

Réseau. L'installation télécharge depuis GitHub (dépôt et Python) et PyPI, puis l'agent appelle l'API Anthropic. [Hypothèse] le wifi de la salle laisse passer ces trois origines et tient vingt installations en même temps. Parade : un partage de connexion.

## 4. Les commandes

Une seule entrée, `uv run kit`. `uv run kit` seul affiche cette liste.

| Commande | Ce qu'elle fait | Lot |
|---|---|---|
| `uv run kit installer` | Installe Python et les dépendances, vérifie l'empreinte des données, demande la clé si elle manque. Se relance sans risque. | 1 |
| `uv run kit cle` | Enregistre ou remplace la clé d'API. L'étudiant colle la clé dans le terminal, il n'édite aucun fichier. | 1 |
| `uv run kit controle` | Vérifie l'installation point par point. Chaque ligne en échec dit quoi faire. Dernière ligne : `RÉUSSITE` (code 0) ou `ÉCHEC` (code 1). `--hors-ligne` saute l'appel au modèle. | 1 |
| `uv run kit agent "question"` | Pose une question à l'agent de l'équipe. Affiche la réponse, les jetons consommés et leur coût estimé. Écrit une trace. | 1 |
| `uv run kit pousser` | Envoie les traces vers le dépôt de l'équipe : les enregistre, récupère le travail des coéquipiers, pousse. Ne touche à aucun autre fichier. | 2 |
| `uv run kit evaluer` | Fait passer une batterie de questions à l'agent. Affiche la justesse, l'abstention et la frugalité. Écrit une trace. | 2 |
| `uv run kit noter` | Note après coup une trace d'évaluation, à partir d'un corrigé. | 2 |
| `uv run kit bilan` | Tableau des exécutions passées et consommation estimée de l'équipe. | 2 |

**La clé vit hors du dépôt**, dans un fichier du dossier personnel de l'étudiant. Une clé qui n'est pas dans l'arbre de travail ne peut pas partir dans un commit, même par `git add .`. C'est la seule prévention disponible : la protection de GitHub contre la publication de secrets ne couvre pas les dépôts privés d'un plan gratuit [Fait, documentation GitHub].

Ce que `controle` vérifie :

- données présentes, empreinte conforme à celle du fichier contrôlé le 11 novembre [Fait] ;
- tableau chargé à la forme attendue, 4 271 lignes et 256 colonnes [Fait] ;
- dictionnaire des colonnes cohérent avec le fichier ;
- identifiant d'équipe valide (§ 7.2) ;
- clé présente, et aucun motif de clé dans un fichier suivi par git ;
- dossier `kit/` identique à la version publiée (lot 2) ;
- `traces/` inscriptible ;
- un appel minimal au modèle aboutit.

## 5. Ce que le kit fournit

```
kit/           fourni ; on n'y touche pas
equipe/        à écrire par l'équipe (§ 6)
traces/        écrit par le kit, versionné (§ 7)
donnees/       le fichier publié et son dictionnaire officiel, versionnés, jamais modifiés
equipe.toml    identifiant de l'équipe, lien de la réutilisation publiée
JOURNAL.md     journal de bord de l'équipe
README.md      trois commandes, puis les rubriques que l'équipe remplit
```

### 5.1 Le chargement du fichier

`kit.donnees.charger()` rend le tableau complet, 256 colonnes typées. Il règle le séparateur, la virgule décimale des colonnes de dosage, et garde en texte les cellules cliniques à valeurs multiples.

Il ne fait rien d'autre : aucun recodage, aucun filtrage, aucune colonne retirée ou renommée, aucune valeur manquante comblée. Ce que les valeurs veulent dire reste à la charge de l'équipe.

Le fichier est dans le dépôt [Décision] : jeu « Allergen Chip Challenge », Société Française d'Allergologie, DOI 10.60597/j5fe-g420, Licence Ouverte 2.0 [Fait]. Le README cite la source et la licence. Git ne doit jamais convertir ses fins de ligne : sous Windows, l'empreinte changerait et `controle` échouerait pour tout le monde. Le fichier est donc déclaré binaire dans `.gitattributes`.

### 5.2 Le dictionnaire des colonnes par type de puce

`kit/colonnes.csv`, une ligne par colonne : `colonne`, `bloc` (`clinique` ou `dosage`), `lecture` (`nombre` ou `texte`, selon la façon dont le chargement lit la colonne, sans rien dire de son sens), puis une colonne `puce_<nom>` par type de puce, vraie si la colonne est renseignée pour au moins un patient de cette puce. `kit.donnees.colonnes()` le rend sous forme de tableau.

Lot 1 : le fichier est livré figé. Lot 2 : le script qui le génère, et le test qui vérifie qu'il se régénère à l'identique.

Il ne porte ni description, ni famille d'allergènes, ni seuil, ni unité. Le dictionnaire officiel est dans `donnees/`, tel que publié, sans commentaire.

### 5.3 L'agent minimal

`equipe/agent.py`, une vingtaine de lignes lisibles : un `CodeAgent` de smolagents [Décision], qui écrit lui-même son code pandas. Il reçoit le tableau, aucun outil d'analyse, une consigne neutre d'une phrase. Il répond déjà à une question simple. C'est le point de départ de l'équipe, qui le modifie librement.

**Le contrat.** Une fonction `repondre(question)` qui rend une réponse en trois champs. Le reste du kit ne connaît que cette fonction.

| Champ | Valeurs |
|---|---|
| `statut` | `reponse` ou `abstention` |
| `valeur` | un nombre ou un texte ; vide en cas d'abstention |
| `justification` | une à trois phrases |

Le kit fixe la forme d'une abstention. Il ne dit jamais quand s'abstenir : c'est le travail de l'équipe [Décision 2].

**Ouvert, puis fermé.** L'accès de l'agent aux données tient en deux lignes de `equipe/agent.py`, signalées par un commentaire : celle qui lui passe le tableau, celle qui l'autorise à importer pandas. Tant qu'elles sont là, l'agent est ouvert et les outils de l'équipe ne sont qu'une option parmi d'autres pour lui. L'équipe qui les retire ferme l'accès : l'agent écrit toujours du code, mais il n'atteint plus les données que par les outils de `equipe/outils/`. Jusqu'où fermer est une décision de l'équipe, qu'elle justifie par ses deux scores. Remplacer le `CodeAgent` par un `ToolCallingAgent`, qui n'exécute aucun code, est le bout de ce chemin : une ligne à changer, les mêmes outils.

**Ce que cela engage, et que le README dit en clair.**

- Un agent ouvert exécute sur le portable de l'étudiant du code que personne n'a relu. Ce code peut lire et écrire des fichiers du compte, et accéder au réseau [Fait, testé le 13 novembre].
- La fermeture retire ces accès directs [Fait, testé]. Elle réduit ce que l'agent peut faire ; ce n'est pas un bac à sable, et la documentation de smolagents le dit de son propre interpréteur.
- Un outil qui rend le tableau lui-même rouvre tout [Fait, testé]. Un outil rend des valeurs simples : un nombre, un texte, une courte liste.
- La seule isolation réelle est une machine distante (§ 3).

Le test qui rejoue ces constats n'entre dans le dépôt qu'après relecture par Adrien [Décision].

**Le repli.** `kit/boucle_maison.py`, une boucle d'outils d'une soixantaine de lignes [Décision], même contrat, activée en changeant une ligne. Elle n'exécute aucun code écrit par le modèle : c'est un mode dégradé, qui ne sait qu'appeler les outils de l'équipe.

**La consommation** [Décision 4].

- Par défaut : huit étapes au plus par question, sorties tronquées, deux modèles proposés. Haiku 5.5 pour le développement, Sonnet 5.5 pour les passes officielles ; les identifiants sont ceux que `tester-la-stack.py` valide.
- Ce ne sont pas des verrous. Le plafond du workspace reste la seule vraie limite.
- Limite de workspace atteinte (erreur 400 [Fait]) : erreur finale. Le kit affiche « cagnotte épuisée » et renvoie vers Adrien, écrit la trace, ne retente rien, dans les deux moteurs.
- Saturation passagère : deux nouvelles tentatives espacées, pas plus.

### 5.4 Le squelette du harnais d'évaluation (lot 2)

`uv run kit evaluer <batterie.toml>` lit une batterie, appelle `repondre` pour chaque question, compare et note. Sans argument, il fait passer toutes les batteries de `equipe/questions/`.

Une question, en TOML :

```toml
[[question]]
id = "q01"
texte = "…"
type = "nombre"      # nombre | choix | sans-reponse
attendu = 12         # absent pour sans-reponse
tolerance = 0
```

- Sept verdicts : juste, faux, abstention fondée, abstention à tort, réponse inventée, illisible, erreur.
- Deux scores, jamais fondus en un seul [Décision 2]. **Justesse** : réponses justes sur questions qui ont une réponse. **Abstention** : abstentions fondées sur questions sans réponse.
- Une mesure de **frugalité**, affichée à côté des scores et jamais fondue avec eux : jetons lus et écrits, coût estimé et durée, au total et par question.
- Le modèle se choisit par `--modele`, parmi ceux de `kit/reglages.toml`. Par défaut, celui du développement.
- Une limite de dépense atteinte arrête la batterie à la question en cours : la trace garde ce qui a été fait.
- La comparaison est mécanique. Aucun modèle ne juge les réponses : cela coûterait des jetons et changerait d'une exécution à l'autre.
- Une batterie peut arriver sans corrigé : un identifiant et un texte par question, rien d'autre. Le harnais d'évaluation exécute et enregistre, sans noter. La notation vient ensuite : `uv run kit noter <trace> --corrige <corrigé.toml>` relit la trace, affiche les verdicts et les scores, et n'appelle pas le modèle. On peut ainsi distribuer des questions sans dire lesquelles sont sans réponse.
- `--exemple` fait tourner trois questions sur une table inventée de douze lignes (`kit/exemple/`), pour montrer le format sans toucher au fichier réel.
- `--officielle` refuse de tourner si le travail n'est pas enregistré et poussé, puis marque la trace. L'état d'une passe officielle existe donc toujours sur GitHub.

### 5.5 Les tests

`uv run pytest`, tous verts à la livraison, sans réseau ni clé. Ils couvrent le chargement (sur la table inventée), le contrat de réponse, les traces (écrites même en cas d'erreur, anonymes, sans collision de noms), et l'erreur de limite, jamais retentée. Au lot 2 s'ajoutent la notation avec un faux agent et la régénération du dictionnaire.

Aucun test ne porte sur le contenu du fichier réel au-delà de sa forme et de son empreinte. Le kit ne livre aucun test rouge « à faire passer » : il dirait quels outils écrire.

### 5.6 Le reste

- `tester-la-stack.py` et `verifier-ma-machine.py` [Fait : ils existent], rangés dans `kit/` tels quels.
- `JOURNAL.md` et `README.md`, réduits à leurs titres, plus trois rubriques écrites par le kit dans le README : la source et la licence des données, ce que le kit enregistre (§ 7.5), ce qu'un agent ouvert peut faire (§ 5.3).

## 6. Ce que le kit laisse à faire

| À l'équipe | Où | État à la livraison |
|---|---|---|
| Les outils de l'agent | `equipe/outils/`, un fichier par outil | vide, plus un exemple de syntaxe sans rapport avec l'analyse |
| La consigne, règle d'abstention comprise | `equipe/consigne.md` | une phrase neutre |
| L'accès de l'agent aux données | `equipe/agent.py` | ouvert |
| Les questions de contrôle | `equipe/questions/`, un fichier par lot | vide |
| L'analyse | `equipe/analyse/` | vide |
| La documentation | `README.md`, `JOURNAL.md` | titres seuls |

Un outil est une méthode en laquelle l'équipe a confiance : écrite une fois, testée sans appeler le modèle, donc sans jeton.

Un fichier par outil et par lot de questions : quatre débutants qui modifient le même fichier, c'est un conflit git par heure.

**La règle « aucune réponse ».** Le dépôt ne contient aucune question de contrôle sur le fichier réel, aucune valeur attendue, aucun outil d'analyse, aucune règle d'abstention, aucune remarque sur ce que les données permettent de conclure. Les seuls faits sur le fichier réel sont son empreinte, sa forme et le dictionnaire du § 5.2. Adrien relit le dépôt avec cette règle en tête avant de le publier.

## 7. Les traces

[Décision, 11 novembre] C'est une contrainte de conception. Les traces se collectent pendant la semaine, jamais après, et le kit les produit seul.

### 7.1 Ce qui s'écrit, et quand

| Déclencheur | Écrit dans | Contenu |
|---|---|---|
| chaque `kit agent` | `traces/appels/<jour>/` | horodatage, équipe, état, modèle, question, réponse, étapes de l'agent (code écrit, résultats tronqués), jetons, durée, erreur éventuelle |
| chaque `kit evaluer` | `traces/evaluations/<jour>/` | les deux scores, le décompte des verdicts, la batterie et son empreinte, le modèle, les jetons, puis le détail question par question |
| chaque état nouveau de `equipe/` | `traces/etats/<empreinte>/` | copie de `agent.py`, `consigne.md`, `outils/`, `questions/` |

Chaque trace cite l'empreinte de l'état qui l'a produite, le commit git s'il y en a un, et la version de son propre format. L'écriture a lieu même si l'exécution échoue ou est interrompue.

Ce que cela donne :

- des scores horodatés par équipe à chaque exécution ;
- les états successifs du travail, sans dépendre de la discipline git des étudiants ;
- les erreurs de l'agent gardées avec leurs étapes, sans que personne ait à penser à faire une capture ;
- l'agent du mardi et celui du vendredi, tous deux enregistrés avec leurs scores.

### 7.2 Rien qui porte un nom

- L'équipe s'appelle `accueil` (avant la constitution des équipes) ou `equipe-` suivi d'un chiffre de 1 à 9. Tout autre identifiant fait échouer `controle`. Le kit ne connaît pas le nombre d'équipes : il se décide lundi, entre cinq et sept [Décision].
- Les champs forment une liste fermée. Ni nom d'utilisateur, ni nom de machine, ni identifiant durable par personne, ni auteur git.
- Avant toute écriture, le chemin du dossier personnel, le nom d'utilisateur du système et tout motif de clé d'API sont remplacés. Un test le vérifie.
- Limite assumée : le texte libre (questions tapées, journal, commentaires de code). La règle est écrite dans le README et le journal : on signe en équipe, jamais d'un prénom. Aucune machine ne la vérifie.
- L'historique git porte les auteurs. Il appartient aux étudiants ; la collecte d'Adrien l'exporte sans eux.

### 7.3 Sans conflit

Un fichier par exécution, nommé par son horodatage et un suffixe aléatoire. Aucun fichier commun que chacun complète : quatre machines poussent leurs traces sans jamais se gêner. Les tableaux de synthèse se calculent à la demande (`kit bilan`), ils ne se stockent pas.

Sans conflit ne veut pas dire sans ordre : un push est refusé tant qu'on n'a pas récupéré celui des coéquipiers. `uv run kit pousser` fait les gestes dans le bon ordre, et recommence si un coéquipier a poussé entre-temps.

### 7.4 Jusqu'à Adrien

`traces/` est versionné et part à chaque `git push`. Le maillon faible est là : pousser reste un geste humain. Trois parades.

- `uv run kit pousser` ramène l'envoi des traces à une commande.
- À partir du lot 2, `controle` et `bilan` signalent les traces qui n'ont pas été poussées.
- Une passe officielle exige un état poussé (§ 5.4).
- Un rituel de fin de demi-journée, à la main d'Adrien.

Contrat de collecte : tout ce dont le dossier de valorisation a besoin se trouve à des chemins fixes dans chaque dépôt d'équipe. `traces/`, `JOURNAL.md` (une phrase par jour, signée de l'équipe), `equipe.toml` (lien de la réutilisation publiée). Les noms, photos et citations attribuées vivent ailleurs [Décision 6].

### 7.5 Dit aux étudiants

Le README explique en clair ce que le kit enregistre, où, et à quoi cela servira. Une semaine sur l'honnêteté des données ne collecte rien en douce.

## 8. Dépôts, clés, mises à jour

**L'organisation** [Décision, 13 novembre]. `sprint-dojo`, plan gratuit. Permission de base : aucune. Les membres ne créent pas de dépôt.

| Dépôt | Visibilité |
|---|---|
| `efrei-lxp-2026-11-allergylab-kit` | public |
| `efrei-lxp-2026-11-allergylab-equipe-1` à `-equipe-7` | privés |

**Le dépôt du kit est public, et le kit s'y développe directement** [Décision] : le cadrage et les pièges restent dans le dépôt de production, hors de portée de l'outil qui écrit le kit. Un clone sans authentification est une condition du scénario : vingt étudiants qui configurent un accès GitHub à 9h30, c'est l'heure perdue.

**Les dépôts d'équipe sont privés par défaut** [Décision]. Publier le travail de vingt étudiants est une décision qui leur appartient. Sept sont créés avant lundi à partir du kit, avec le même historique et leur `equipe.toml` déjà réglé ; ceux qui ne trouvent pas d'équipe lundi restent vides. Lundi, une fois les équipes constituées, Adrien donne à chaque étudiant l'accès au dépôt de son équipe ; chacun y redirige alors son clone du matin (une commande) et garde ses premières traces.

**Le vendredi** [Décision]. Le passage en public est un geste volontaire de l'équipe, et il précède la publication de la réutilisation sur data.gouv.fr : dans l'autre sens, le lien publié mène à une page d'erreur. En fin de semaine, chaque équipe transfère son dépôt vers le compte d'un de ses membres ou en garde un fork ; l'organisation conserve sa copie.

**La frontière** [Décision]. Rien du dépôt privé de production pédagogique n'entre dans `sprint-dojo` : ni corrigé, ni sujet, ni remote partagé.

**Les correctifs en cours de semaine.** Adrien les fusionne dans les dépôts d'équipe ; les équipes n'ont qu'un `git pull` à faire. Cela passe sans conflit parce que chacun reste chez soi : les équipes ne touchent pas à `kit/`, et le kit ne touche plus à `equipe/`, `equipe.toml`, `README.md` ni `JOURNAL.md`.

**Les clés.** Un workspace et une clé par équipe [Décision]. Lundi à 9h30 les équipes n'existent pas encore : il faut une clé d'accueil, sur un workspace à part plafonné à quelques dollars, commune aux vingt étudiants et révoquée lundi soir. Une clé se colle, elle ne se recopie pas : prévoir le canal qui la diffuse. Un agent ouvert peut lire la clé comme n'importe quel fichier du compte (§ 5.3) : le plafond du workspace et la révocation sont la vraie protection.

**Les cagnottes** [Décision, 13 novembre]. Une équipe ne reçoit pas tout son budget d'un coup. Elle a une cagnotte d'essais, ouverte lundi ; une cagnotte pour le final, ouverte par Adrien avant la restitution ; et elle peut demander une rallonge, prise sur une réserve commune. Les montants sont annoncés lundi. Ce qu'une équipe n'a pas dépensé en essais lui reste pour le final [Décision]. Une cagnotte n'est pas un réglage du kit : c'est le plafond du workspace, qu'Adrien relève dans la console. Épuiser sa cagnotte d'essais reste une faute de conception [Décision 4] : la rallonge se demande, elle ne se doit pas. La demande s'écrit dans `JOURNAL.md`, en trois lignes signées de l'équipe : ce qui a consommé la cagnotte, ce qui va changer, le montant demandé.

**Le budget visible.** Chaque exécution affiche ses jetons et son coût estimé, aux tarifs du dossier de passation. À partir du lot 2, `bilan` additionne les traces présentes dans le dépôt et les compare aux cagnottes annoncées : c'est une estimation, pas un relevé. Le relevé exact est dans la console, qu'Adrien seul consulte.

**Pousser sur GitHub** demande une authentification et un accès au dépôt d'équipe. Les deux tombent après 10h30, hors de l'heure jugée. [Hypothèse] le terminal intégré de VS Code s'en charge sur les trois systèmes ; à vérifier avant lundi.

## 9. Critère de fin

**Lot 1.** Sur une machine vierge :

```
git clone https://github.com/sprint-dojo/efrei-lxp-2026-11-allergylab-kit
cd efrei-lxp-2026-11-allergylab-kit
uv run kit installer
uv run kit controle
uv run kit agent "Combien de lignes compte le tableau ?"
uv run pytest
```

- `installer` rend le code 0. Sans terminal interactif, il lit la clé dans une variable d'environnement.
- `controle` finit par `RÉUSSITE` et rend le code 0.
- `agent` affiche une réponse, rend le code 0, et `traces/appels/` contient exactement un fichier valide.
- `pytest` est vert.
- Contre-épreuve : clé retirée, puis fichier de données altéré. `controle` finit chaque fois par `ÉCHEC`, rend le code 1, et nomme la cause.

**Sur trois systèmes.** Une matrice GitHub Actions, un job par système (macOS, Windows, Linux), rejoue ces commandes avec le seul Python que uv télécharge, sans cache. La partie sans clé tourne à chaque push ; la partie avec clé se déclenche à la main. C'est le seul moyen de prouver Windows et Linux avant lundi sans avoir les machines sous la main, et elle ne coûte rien sur un dépôt public [Fait]. La matrice dit où l'installation est prouvée ; les autres configurations (Mac Intel, Windows sur ARM) passent par le § 3 si elles échouent.

Les tests couvrent quatre pièges d'environnement : un chemin avec espaces et accents, l'affichage des accents dans la console Windows, les fins de ligne, un dossier sans git.

**Lot 2.** `uv run kit evaluer --exemple` affiche les deux scores et écrit une trace d'évaluation. `uv run kit bilan` la liste.

## 10. Lots et calendrier proposé

| Lot | Contenu | Accepté au plus tard |
|---|---|---|
| 1 | Installation, contrôle, données, dictionnaire figé, agent minimal et repli, clé, traces d'appels et d'états, tests, matrice | dimanche 15 novembre au soir |
| 2a | `pousser`, signalement des traces non poussées, portée de `CLAUDE.md` dans un dépôt d'équipe | mardi 17 novembre |
| 2b | Harnais d'évaluation, batterie d'exemple, `noter`, `bilan`, option `--officielle` | mercredi 18 novembre au matin |
| 3 | `--donnees <fichier>` pour interroger l'agent sur un autre fichier que celui du dépôt ; `--adversaire <equipe>` pour marquer dans la trace qui a posé la question, quinze questions au plus par adversaire et par jour, la seizième est refusée [Décision] | mardi 17 novembre au soir |

Si le temps manque, on sacrifie dans cet ordre : l'option `--officielle`, puis `bilan`. Jamais `controle`, jamais les traces d'appels.

Reportés sans date : le `.devcontainer`, le générateur du dictionnaire, le contrôle de `kit/` intact.

## 11. Hypothèses encore ouvertes

Résolues depuis le 11 novembre : dépôt du kit public, organisation plutôt que forks, licence du fichier.

1. Une clé d'accueil sur un sixième workspace sert la première heure. Les limites de débit de l'organisation Anthropic supportent vingt étudiants qui posent leur première question dans les mêmes dix minutes : à lire dans la console.
2. Les « comptes gratuits » de la décision 5 sont les assistants en ligne que les étudiants utilisent déjà pour réfléchir et prototyper. Le kit n'en dépend pas ; tout appel de l'agent passe par la clé.
3. Python 3.12 convient à smolagents 1.26.0.
4. Le wifi de la salle laisse passer GitHub, PyPI et l'API Anthropic.
5. Haiku 5.5, dans un `CodeAgent`, répond à une question simple sur le tableau en huit étapes au plus.
6. Le dictionnaire officiel est couvert par la même licence que le fichier de données.
7. Le terminal intégré de VS Code suffit pour pousser sur un dépôt privé.
8. Le montant des cagnottes se fixe après la mesure du coût réel d'une question, au premier appel de l'agent minimal.

## 12. Hors périmètre

- La batterie officielle, le protocole des passes et le déroulé du mercredi.
- La création des dépôts, les invitations, l'attribution des accès du lundi et le script de collecte d'Adrien.
- Le banc de comparaison Featherless [Décision : un banc, pas un moteur]. Le harnais d'évaluation prend le modèle en paramètre, rien ne l'empêche ; son usage se cadre avec la batterie.
- L'inférence locale [Décision : bonus facultatif], au-delà de la présence de `verifier-ma-machine.py`.
- La grille d'évaluation et la note.
- Le cours Hugging Face et la publication sur data.gouv.fr.

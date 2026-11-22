# Interface de Christian AI

L'interface web de l'agent de l'équipe 1 : React, TypeScript et Vite, sans autre bibliothèque que les icônes `lucide-react`. Une seule police (Arial), une seule couleur d'accent, un thème clair et un thème sombre qui suivent le réglage du système.

Le serveur local doit tourner d'abord, depuis la racine du dépôt :

```
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Puis, dans ce dossier :

```
npm install
npm run dev      l'interface sur http://127.0.0.1:5173
npm run build    vérifie le TypeScript et construit dist/
```

Le serveur de développement renvoie les adresses `/api` vers `127.0.0.1:8000` (`vite.config.ts`).

| Fichier | Rôle |
|---|---|
| `src/App.tsx` | la mise en page, la navigation, l'envoi des questions, la lecture à voix haute |
| `src/Chat.tsx` | la conversation, l'indicateur « Christian AI réfléchit… », la zone de saisie et son micro |
| `src/useDictation.ts` | la dictée en français, avec la reconnaissance vocale du navigateur (Web Speech API), sans bibliothèque ni modèle ; dans Chrome, le français s'installe sur l'ordinateur au premier clic, puis la dictée marche sans internet |
| `src/Mascot.tsx` | l'avatar de Christian AI : au repos, en réflexion (anneau et bulle de pensée), en lecture |
| `src/DataPage.tsx` | les chiffres clés, les mois de prélèvement, le calendrier pollinique |
| `src/AboutPage.tsx` | comment l'agent répond, et ce qu'il faut savoir |
| `src/api.ts` | les appels au serveur local et leurs types |
| `src/styles.css` | les couleurs (variables CSS, clair et sombre) et toute la mise en forme |

`app.py` est l'ancienne interface Streamlit, gardée pour mémoire.

Le mode d'emploi complet est dans le [README à la racine du dépôt](../README.md).

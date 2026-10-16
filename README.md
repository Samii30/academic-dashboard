# 🎓 Dashboard de Suivi Académique & Planning d'Études (AcademicTrack)

> **Projet Étudiant Portfolio — Licence 1 Informatique**  
> Une application web fullstack légère, moderne et réactive conçue pour centraliser le suivi des notes universitaires, le calcul automatique des moyennes pondérées par coefficient, l'importation automatique de plannings iCalendar (ICS), la simulation de notes prévisionnelles et la gestion complète du planning académique.

---

## 🚀 Présentation & Contexte

En tant qu'étudiant en informatique, la gestion rigoureuse des Unités d'Enseignement (UE), des coefficients universitaires, des partiels et des devoirs est primordiale pour réussir son année.  
Ce projet a été développé pour répondre à ce besoin concret avec une architecture propre respectant les bonnes pratiques logicielles dès la première année :
- **Architecture API-First & SPA réactive** : Requêtes asynchrones via la Fetch API de JavaScript vanilla (aucun rechargement de page nécessaire).
- **Backend robuste et typé** avec **Python 3**, **FastAPI** et **SQLAlchemy 2.0**.
- **Base de données relationnelle** locale avec **SQLite** pour une autonomie totale (`academic_dashboard.db`).
- **Module d'Importation Automatique ICS (iCal)** : Synchronisation directe via URL (ADE Campus, Moodle, ENT) ou fichier `.ics` avec détection automatique des UE et priorisation intelligente des examens.
- **Data Visualisation interactive** intégrée avec **Chart.js** (graphiques en barres et en anneau).
- **Simulateur de notes et de partiels** pour tester des hypothèses de notes en temps réel.
- **Frontend moderne & ergonomique** en **HTML5**, **CSS3 (Grid/Flexbox avec Dark Mode natif)** et modales accessibles.

---

## 🛠️ Stack Technique

| Couche | Technologie | Rôle |
|---|---|---|
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/) | API REST asynchrone haute performance |
| **Serveur ASGI** | [Uvicorn](https://www.uvicorn.org/) | Serveur d'exécution asynchrone |
| **ORM** | [SQLAlchemy 2.0](https://www.sqlalchemy.org/) | Modélisation objet-relationnelle et requêtes typées |
| **Validation** | [Pydantic v2](https://docs.pydantic.dev/) | Validation stricte des schémas de données |
| **Base de Données** | [SQLite 3](https://www.sqlite.org/) | Stockage persistant sans serveur (`academic_dashboard.db`) |
| **Parser iCal** | Python Pur (RFC 5545) | Dépliage, parsing des événements et extraction d'UE |
| **Data Viz** | [Chart.js 4.x](https://www.chartjs.org/) | Graphiques interactifs (Moyennes UE & Coefficients) |
| **Frontend** | HTML5 / CSS3 / Vanilla JS | Interface réactive avec Dark Mode et modales interactives |
| **Templates** | Jinja2 | Rendu serveur de la structure d'accueil |

---

## 📂 Architecture du Projet

```text
Dashboard de Suivi Académique & Planning d'Études/
├── app/
│   ├── __init__.py           # Package Python
│   ├── database.py           # Configuration SQLite, sessionmaker & init_db
│   ├── models.py             # Modèles de tables SQLAlchemy (modules, grades, tasks)
│   ├── schemas.py            # Schémas de validation Pydantic v2 (dont ICSImport)
│   ├── ics_parser.py         # Parser iCalendar RFC 5545 & extraction d'UE
│   └── main.py               # Routes API REST (CRUD, import ICS, calculs)
├── static/
│   ├── css/
│   │   └── style.css         # Thème moderne Dark Mode, Grid, Flexbox, Modales & Graphiques
│   └── js/
│       └── app.js            # Logique client (Fetch API, Chart.js, simulateur, import ICS)
├── templates/
│   └── index.html            # Structure HTML5 avec Chart.js, simulateur et modales
├── academic_dashboard.db     # Base SQLite avec persistance complète des données
├── requirements.txt          # Dépendances Python du projet
└── README.md                 # Documentation d'installation et d'utilisation
```

---

## ⚡ Fonctionnalités Clés

### 1. Import Automatique de Planning (ICS / iCal)
- **Bouton dédié dans le header** : *« 📅 Importer mes cours (ICS) »*.
- **Double mode de saisie** :
  1. *Lien URL direct* (ADE Campus, ENT université, Moodle, Google Agenda, Webcal).
  2. *Téléversement de fichier local* `.ics`.
- **Analyse sémantique intelligente** :
  - Détection automatique des codes d'Unités d'Enseignement (ex: `INF101`, `MAT102`).
  - Détection automatique des examens, partiels, devoirs surveillés et soutenances avec attribution automatique de la priorité **Haute 🔴**.
  - Gestion de l'idempotence (aucun doublon créé lors de ré-importations successives).

### 2. Gestion des Unités d'Enseignement (UE)
- **Ajout de module** manuel ou automatique via ICS.
- **Affichage dynamique** sous forme de cartes élégantes avec code UE mis en valeur.
- **Suppression d'un module** avec suppression en cascade de toutes ses notes associées.

### 3. Gestion des Évaluations & Calculs Dynamiques
- **Ajout de notes** directement depuis la carte du module ou via le bouton principal (note /20, coefficient, intitulé, date).
- **Moyenne par module** calculée automatiquement et mise à jour en temps réel avec indicateur visuel (vert si $\ge 10/20$, rouge si $< 10/20$).
- **Moyenne Générale Pondérée** : calcul universitaire réel pondéré par le coefficient de chaque module.
- **Taux de Réussite** : pourcentage de modules actuellement validés ($\ge 10/20$).

### 4. Planning d'Études & Tâches
- **Création d'une tâche** : Titre, date d'échéance optionnelle, niveau d'urgence (`Haute 🔴`, `Moyenne 🟡`, `Basse 🟢`).
- **Modification complète d'une tâche** : Bouton `✏️` ouvrant un formulaire modal pour corriger le titre, la date ou la priorité sans avoir à recréer la tâche (`PUT /api/tasks/{id}`).
- **Cochage interactif** : Case à cocher mettant à jour instantanément la tâche en base via l'API `PATCH`.
- **Compteurs dynamiques** : Affichage en direct du nombre de tâches en cours et des tâches urgentes restantes.

### 5. Graphiques Statistiques Interactifs (Chart.js)
- Visualisation interactive avec basculement en 1 clic :
  - **Moyennes par UE** : Graphique en barres colorées (vert pour les UE validées $\ge 10/20$, rouge si $< 10/20$).
  - **Répartition des Coefficients** : Graphique en anneau (*Doughnut*) affichant le poids relatif de chaque matière dans le semestre.

### 6. Simulateur de Notes & Partiel
- Permet de tester en direct des scénarios d'évaluation :
  - Sélection de la matière cible.
  - Saisie d'une note hypothétique (ex: `15/20`) et de son coefficient (ex: `3.0`).
  - **Calcul en temps réel** de l'impact direct :
    - Nouvelle moyenne projetée du module et delta de points ($\pm X.XX\text{ pts}$).
    - Nouvelle moyenne générale projetée du semestre et delta global.

---

## 📡 Endpoints de l'API REST

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/` | Page d'accueil du Dashboard |
| `GET` | `/api/health` | Vérification de la santé du serveur et de SQLite |
| `GET` | `/api/summary` | Synthèse globale (Moyenne générale, nombre d'UE, taux de réussite) |
| `POST` | `/api/import-ics` | **Importation automatique iCalendar** (URL ou fichier `.ics`) |
| `GET` | `/api/modules` | Liste des modules avec notes et moyenne calculée |
| `POST` | `/api/modules` | Création d'un module (contrôle d'unicité du code UE) |
| `DELETE` | `/api/modules/{id}` | Suppression d'un module et de ses notes en cascade |
| `GET` | `/api/grades` | Liste des notes (avec filtre optionnel `?module_id=...`) |
| `POST` | `/api/grades` | Enregistrement d'une nouvelle note |
| `DELETE` | `/api/grades/{id}` | Suppression d'une note |
| `GET` | `/api/tasks` | Liste ordonnée des devoirs et révisions |
| `POST` | `/api/tasks` | Création d'une nouvelle tâche |
| `PUT` | `/api/tasks/{id}` | Modification complète d'une tâche (titre, date, priorité) |
| `PATCH` | `/api/tasks/{id}` | Bascule rapide de l'état fait/non fait |
| `DELETE` | `/api/tasks/{id}` | Suppression d'une tâche |
| `GET` | `/docs` | Documentation Swagger OpenAPI interactive |

---

## ⚙️ Installation & Démarrage Rapide

### 1. Cloner ou ouvrir le dossier du projet
```bash
cd "Dashboard de Suivi Académique & Planning d'Études"
```

### 2. Activer l'environnement virtuel
- **macOS / Linux :**
  ```bash
  source venv/bin/activate
  ```
- **Windows (PowerShell) :**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```

### 3. Démarrer le serveur de développement
```bash
uvicorn app.main:app --reload
```

Accédez ensuite à l'application dans votre navigateur :
- 🌐 **Dashboard Web** : [http://127.0.0.1:8000](http://127.0.0.1:8000)
- 📖 **Documentation Swagger** : [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

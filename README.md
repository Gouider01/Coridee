# CoRide 

**Application web de covoiturage** qui met en relation les personnes qui ont une voiture et celles qui font le même trajet, pour voyager ensemble en partageant les frais, de façon simple et sûre.

> Projet Software Engineering – 3e année Intelligence Artificielle · ESPRIT · 2026-2027
> Équipe **Blackberry**

---

## Le problème

Chaque jour, beaucoup de personnes font le même trajet pour aller au travail, étudier ou voyager entre les villes, souvent dans des transports en commun bondés, pendant que des voitures circulent avec des places vides.

Aujourd'hui, le covoiturage s'organise surtout dans des groupes sur les réseaux sociaux :
- aucune vérification de l'identité des conducteurs ni des papiers des voitures ;
- aucune gestion des places disponibles ;
- des prix fixés sans repère ;
- aucun moyen de savoir si un conducteur ou un passager est fiable.

## Notre solution

CoRide est une plateforme unique et sécurisée où :
- chaque utilisateur est **vérifié** à l'inscription ;
- seules les **voitures en règle** peuvent proposer des trajets ;
- les **places et les réservations** sont gérées automatiquement ;
- un **prix juste** est suggéré pour chaque trajet ;
- conducteurs et passagers peuvent **discuter** et **s'évaluer** après le trajet.

---

## Utilisateurs

| Utilisateur | Rôle |
|---|---|
| **Passager** | Cherche un trajet, réserve une place, discute avec le conducteur, donne son avis |
| **Conducteur** | Enregistre sa voiture, publie des trajets, accepte les passagers |
| **Administrateur** | Gère les comptes, vérifie les voitures, surveille les contenus |

---

## Modules et équipe

| Module | Ce qu'il permet | Responsable | Branche |
|---|---|---|---|
| **1. Gestion des utilisateurs** | Inscription, vérification de l'identité, profils, administration des comptes | Alaaeddine Guouider | `Gestion-Utilisateurs` · app `users` |
| **2. Gestion des véhicules** | Enregistrement des voitures et vérification de leurs papiers | Abdallah Salhi | `Gestion-vehicules` · app `vehicles` |
| **3. Gestion des trajets** | Publication des trajets et recherche par les passagers | Wasim Snoussi | `Gestion-Trajets` · app `trips` |
| **4. Gestion des réservations** | Demande, acceptation et annulation des réservations, billet QR code | Selim Aschi | `Gestion-Reservations` · app `reservations` |
| **5. Communication et avis** | Discussion entre conducteur et passager, notes et commentaires | Ahmed Ridha Lazhari | `Gestion-Communication` · app `communication` |

---

## Intelligence artificielle

| Module | Fonctionnalité |
|---|---|
| Utilisateurs | Vérification de l'identité par selfie, contrôle des photos de profil, détection des faux comptes, assistant virtuel |
| Véhicules | Lecture automatique des papiers de la voiture |
| Trajets | Suggestion d'un prix juste pour chaque place |
| Réservations | Recommandation de trajets selon les habitudes du passager |
| Communication et avis | Blocage des messages et commentaires insultants |

---

## Planning

Le projet est réalisé avec la méthode **Scrum**, en 3 sprints de 2 semaines.

| Sprint | Objectif |
|---|---|
| **Sprint 1** | Structure du projet et fonctionnalités de base de chaque module |
| **Sprint 2** | Fonctionnalités métier : filtres, recherche avancée, pagination, rapports PDF, export Excel |
| **Sprint 3** | Intégration de l'intelligence artificielle |

---

## Impact

En remplissant les places vides des voitures, CoRide contribue à :
- **réduire le coût** des déplacements ;
- **diminuer le nombre de voitures** sur les routes et la pollution ;
- **rendre le covoiturage plus sûr** grâce à la vérification des utilisateurs.

---

## Démarrage (développement)

Prérequis : Python 3.10+ et Git.

```bash
git clone https://github.com/Gouider01/Coridee.git
cd Coridee
git checkout <votre-branche>          # ex. Gestion-Trajets

python -m venv .venv
# Windows : .venv\Scripts\activate     ·  Linux/macOS : source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser      # connexion par e-mail
python manage.py runserver            # http://127.0.0.1:8000  ·  admin : /admin/
```

## Architecture

```
CoRide/
├── config/                 # Projet Django : settings.py, urls.py, page d'accueil
├── users/                  # Module 1 - Utilisateurs (modèle User = AUTH_USER_MODEL)
├── vehicles/               # Module 2 - Véhicules
├── trips/                  # Module 3 - Trajets
├── reservations/           # Module 4 - Réservations
├── communication/          # Module 5 - Communication et avis
│   ├── models.py  forms.py  views.py  urls.py  admin.py  tests.py
│   └── templates/<app>/    # templates du module, ex. trips/trip_list.html
├── templates/              # Templates partagés
│   ├── base.html           # Mise en page commune (barre du haut, messages, pied de page)
│   ├── home.html  403.html  404.html
│   └── partials/           # _navbar, _messages, _footer, _field, _form, _form_errors, _seal, _avatar, _icons
├── static/                 # css/coride.css (design system), js/coride.js, fonts/, img/, et static/<app>/
└── requirements.txt
```

Chaque app a déjà son préfixe d'URL (`/users/`, `/vehicles/`, `/trips/`, `/reservations/`, `/communication/`) et son `app_name` : ajoutez vos routes dans `<app>/urls.py`.

### Règles communes

- **Utilisateur** : pour lier un utilisateur, utilisez toujours `settings.AUTH_USER_MODEL`, jamais `User` directement.
  ```python
  from django.conf import settings
  driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trips")
  ```
  Rôles disponibles : `user.is_passenger`, `user.is_driver`, `user.is_administrator`.
- **Modèle d'un autre module** : référencez-le par une chaîne, ex. `"vehicles.Vehicle"`, `"trips.Trip"`.
- **Langue** : toute l'interface est en **anglais**.
- **Templates** : chaque page étend `base.html` (`{% extends "base.html" %}` + `{% block title %}` + `{% block content %}`).
- **Navigation** : pour que votre module apparaisse dans la barre du haut, nommez sa page d'accueil `index` (ex. `path("", views.trip_list, name="index")` dans `trips/urls.py`). Le lien s'affiche automatiquement.
- **Fichiers partagés** (`config/`, `templates/base.html`, `templates/partials/`, `static/css/coride.css`, `static/js/coride.js`) : modification uniquement par pull request vers `main`.

## Design system « Cobalt Night »

Une seule apparence pour toute l'application (pas de Bootstrap), **utilisée par tous les modules**. Fond cobalt avec motif de carreaux de Nabeul, feuilles blanches, rouge CoRide pour l'action principale, accents safran et turquoise. Le sceau à huit pointes marque les personnes vérifiées. Polices : Bricolage Grotesque (titres) et Readex Pro (texte), hébergées dans `static/fonts/`.

| Élément | Utilisation |
|---|---|
| `<div class="page-head">` + `<h1 class="page-head__title">` | En-tête de chaque page |
| `<section class="sheet">` | Bloc de contenu blanc (pas de cartes imbriquées) |
| `btn btn--primary` | **Une seule** action principale (rouge) par écran |
| `btn btn--secondary` / `btn--ghost` / `btn--trust` | Actions secondaires ; `btn--trust` (cobalt) pour vérifier/valider |
| `btn btn--danger` dans `<div class="actions__danger">` | Supprimer, suspendre : toujours en contour et à l'écart |
| `{% include "partials/_field.html" with field=form.x %}` | Un champ avec libellé, aide et **erreurs de saisie** |
| `{% include "partials/_form.html" with form=form submit_label="Save" %}` | Formulaire simple complet |
| `<table class="table">` dans `<div class="sheet sheet--flush"><div class="table-wrap">` | Listes (admin, trajets, réservations…) |
| `badge badge--active` / `--pending` / `--suspended` / `--neutral` | Statuts |
| `{% include "partials/_seal.html" with fired=person.identity_verified %}` | Sceau de vérification à côté d'une personne |
| `{% include "partials/_avatar.html" with person=p size="md" %}` | Photo de profil ou initiales |
| `<svg class="icon"><use href="#i-search"/></svg>` | Icônes (liste dans `partials/_icons.html`) |

Couleurs : rouge CoRide `#c8102e` (action principale), cobalt `#1d3f8f` (confiance, liens), encre `#1b1e24`. Utilisez les variables CSS de `coride.css` (`var(--cobalt-700)`, `var(--s-4)`…) plutôt que des valeurs en dur.
- **Ne jamais committer** `db.sqlite3`, `media/` ni `.venv/` (déjà dans `.gitignore`).

## Workflow Git

1. Travaillez uniquement sur votre branche et dans votre app.
2. Récupérez régulièrement `main` : `git pull origin main`.
3. Commitez vos migrations (`python manage.py makemigrations <app>`).
4. Ouvrez une pull request vers `main` ; elle est relue avant fusion.


---

# Sprint 1: run the integrated version (English)

Branch **`sprint-1`** contains all five modules working together (users, vehicles, trips,
reservations, communication). Use it for the Sprint 1 validation.

## 1. Get the code

First time:
```
git clone https://github.com/Gouider01/Coridee.git
cd Coridee
git switch sprint-1
```
Already cloned:
```
git fetch
git switch sprint-1
git pull
```

## 2. Install (once)

```
python -m venv .venv
.venv\Scripts\activate            # Windows   (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
```
With uv instead: `uv sync`, then put `uv run` in front of every `python manage.py` command below.

## 3. Create the demo data

The database is **not** in Git (`db.sqlite3`, `media/` and `private_media/` are ignored).
Everyone builds the same demo data on their own machine:
```
python manage.py migrate
python manage.py seed_all --reset
```
- Run it **on the morning of the demo**: trip dates are set relative to *now*
  ("tomorrow 07:30", "left 3 hours ago").
- Run it again at any time to start over. `--reset` only touches the demo accounts.
- If `migrate` fails with *table "trips_stop" already exists* (you ran an older Trips version),
  rename your `db.sqlite3` (e.g. `db.sqlite3.old`) and run the two commands again.

## 4. Start the app

```
python manage.py runserver
```
Open http://127.0.0.1:8000. Log in with the **e-mail address**. Every password is **`Demo12345!`**.

## 5. Demo accounts (all `@coride.tn`)

| Account | Who | Use it to show |
|---|---|---|
| `admin@` | administrator | users (verify Rania / Hedi, suspended Marwen), vehicles (accept Nour's), all trips, all bookings, review moderation, admin inbox |
| `nadia@`, `omar@` | administrators | chats with the main admin |
| `leila@` | driver | trips in every state, a pending request from Sami, *Mark as completed* on Tunis → Nabeul |
| `youssef@` | driver | a FULL trip, a finished trip with reviews |
| `amine@` | driver | 2 vehicles, a cancelled trip, a finished trip not yet reviewed |
| `rania@` | driver | identity check still pending |
| `sami@` | passenger | bookings pending / accepted / refused / cancelled, chats, can review Leila |
| `nour@` | passenger | vehicle PENDING (admin accepts it: she becomes a driver), can review Amine |
| `ines@`, `karim@`, `hedi@` | passengers | more bookings; Hedi: ID pending, vehicle with 1 document |
| `marwen@` | passenger | SUSPENDED (cannot log in until an admin reactivates him) |

The command prints this list at the end too.

## 6. Demo plan (one live moment per module)

| Module | Owner | Show live |
|---|---|---|
| 1 Users | Alaaeddine | sign up with a wrong form first (errors), then a valid one; admin verifies Rania, reactivates Marwen, suspends someone |
| 2 Vehicles | Abdallah | Nour adds a vehicle with a bad plate (errors); admin accepts Nour's pending vehicle: she becomes a driver |
| 3 Trips | Wasim | Leila publishes a trip (errors first: past date, same cities, too many seats, price 0), edits it, cancels it; search *Tunis → Sousse*; Leila marks Tunis → Nabeul as completed |
| 4 Reservations | Selim | Sami books a seat, Leila accepts the request (the chat opens), Sami cancels a booking |
| 5 Communication | Ahmed | Sami ↔ Leila chat; Nour opens Amine's completed trip and clicks *Review Amine*; admin deletes a review |

Good to know while demoing:
- **Logout** is in the menu under your name (top right).
- Suspending or deleting an account cancels that person's upcoming trips and bookings.
- Reviews unlock only after the driver marks the trip as completed.

## 7. Tests

```
python manage.py test           # 175 tests, about 5 minutes
python manage.py test trips     # one module only
```

## 8. Git for the rest of the sprint

- `sprint-1` is the shared, integrated branch; `main` will be updated from it with a pull request.
- Fix something in your module: commit on `sprint-1` (or on your branch, then open a pull request to `sprint-1`),
  with a clear message. Commit your migrations.
- Never commit `db.sqlite3`, `media/`, `private_media/` or `.venv/`.

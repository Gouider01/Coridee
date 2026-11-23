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
│   ├── base.html           # Mise en page commune (Bootstrap 5)
│   ├── home.html
│   └── partials/           # _navbar, _messages, _footer, _form (affichage des erreurs)
├── static/                 # css/main.css, js/main.js, img/, et static/<app>/ par module
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
- **Templates** : chaque page étend `base.html` (`{% extends "base.html" %}` + `{% block content %}`) ; formulaires avec `{% include "partials/_form.html" with form=form %}`.
- **Fichiers partagés** (`config/`, `templates/base.html`, `templates/partials/`, `static/css/main.css`) : modification uniquement par pull request vers `main`.
- **Ne jamais committer** `db.sqlite3`, `media/` ni `.venv/` (déjà dans `.gitignore`).

## Workflow Git

1. Travaillez uniquement sur votre branche et dans votre app.
2. Récupérez régulièrement `main` : `git pull origin main`.
3. Commitez vos migrations (`python manage.py makemigrations <app>`).
4. Ouvrez une pull request vers `main` ; elle est relue avant fusion.


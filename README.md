# Presence Test API

API FastAPI de reconnaissance faciale pour la gestion de présence des étudiants.

Ce module est conçu pour etre integre dans une application mobile. Le mobile capture une photo, l'envoie a l'API, et l'API retourne si l'etudiant est reconnu ou non.

## Fonctionnalites

- Reconnaissance faciale a partir d'une photo envoyee par le mobile
- Chargement automatique des etudiants depuis le dossier `students/`
- Creation automatique de la base SQLite `presence.db`
- Creation automatique des fichiers de modeles `.dat` a partir des archives `.bz2`
- Enregistrement des presences avec validation manuelle
- Documentation automatique FastAPI via `/docs`

## Structure du projet

```text
presence_test/
├── app_core.py
├── init_db.py
├── main.py
├── pretrained_model/
├── students/
├── requirements.txt
└── venv/
```

## Prerequis

- Python 3.10+ recommande
- `pip`
- Un environnement Linux est recommande pour l'installation de `dlib`

## Installation

Cloner le projet puis entrer dans le dossier :

```bash
cd presence_test
```

Creer un environnement virtuel si besoin :

```bash
python3 -m venv venv
source venv/bin/activate
```

Installer les dependances :

```bash
pip install -r requirements.txt
```

## Initialisation

Initialiser la base de donnees et charger les etudiants :

```bash
python init_db.py
```

Resultat attendu :

```text
Base de donnees prete : 3 etudiant(s) charge(s)
```

## Lancer le serveur

```bash
uvicorn main:app --reload
```

Le serveur sera disponible sur :

```text
http://127.0.0.1:8000
```

Documentation Swagger :

```text
http://127.0.0.1:8000/docs
```

## API disponible

### 1. Verifier une presence

**Endpoint**

```http
POST /verifier-presence
```

**Parametres**

- `photo` : fichier image envoye en `multipart/form-data`
- `module_id` : identifiant du module

**Exemple curl**

```bash
curl -X POST "http://127.0.0.1:8000/verifier-presence?module_id=1" \
  -F "photo=@students/IDELKADI_Amine_873536829.jpg"
```

**Exemple de reponse**

```json
{
  "match": true,
  "presence_id": 1,
  "nom": "IDELKADI Amine",
  "score": 1.0,
  "message": "Etudiant reconnu, en attente de validation"
}
```

**Cas possible si non reconnu**

```json
{
  "match": false,
  "score": 0.42,
  "message": "Visage non reconnu — utilisez le QR Code"
}
```

### 2. Valider une presence

**Endpoint**

```http
POST /valider-presence/{presence_id}
```

**Exemple curl**

```bash
curl -X POST "http://127.0.0.1:8000/valider-presence/1"
```

**Exemple de reponse**

```json
{
  "status": "Presence validee"
}
```

## Integration mobile

Le module mobile doit :

- capturer une photo du visage
- envoyer la photo au backend en `multipart/form-data`
- envoyer aussi `module_id`
- lire la reponse JSON
- si `match=true`, afficher l'etudiant reconnu
- si `match=false`, proposer une autre methode comme QR code

### Exemple logique mobile

1. L'utilisateur ouvre l'ecran de presence
2. Le mobile prend une photo
3. La photo est envoyee a `POST /verifier-presence`
4. L'API retourne le resultat
5. Si besoin, le surveillant appelle `POST /valider-presence/{presence_id}`

## Format des photos etudiants

Les images dans `students/` doivent respecter ce format de nom :

```text
NOM_Prenom_Matricule.jpg
```

Exemple :

```text
IDELKADI_Amine_873536829.jpg
```

## Notes techniques

- La base utilise SQLite pour simplifier le developpement
- Les modeles `dlib` sont charges automatiquement au demarrage
- Si les fichiers `.dat` n'existent pas encore, ils seront extraits depuis les fichiers `.bz2`
- Les etudiants sont synchronises depuis le dossier `students/` lors de l'initialisation

## Verification rapide

Le projet est considere fonctionnel si :

- `python init_db.py` termine sans erreur
- `uvicorn main:app --reload` demarre correctement
- l'endpoint `/verifier-presence` reconnait une photo connue
- l'endpoint `/valider-presence/{presence_id}` retourne une validation correcte

## Collaboration

Pour integrer ce module dans le projet mobile, les collegues ont surtout besoin de :

- l'URL du backend
- la route `POST /verifier-presence`
- la route `POST /valider-presence/{presence_id}`
- le format de la requete `multipart/form-data`
- le format de la reponse JSON



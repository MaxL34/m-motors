# Guide utilisateur — M-Motors

M-Motors est une application web de gestion et vente/location de véhicules. Elle comporte deux espaces distincts : l'espace client et l'espace administrateur.

---

## Accès à l'application

L'application est accessible à l'adresse : **https://thorough-freedom.up.railway.app**

---

## Espace client

### Créer un compte

1. Cliquer sur **S'inscrire**
2. Remplir le formulaire : prénom, nom, e-mail, mot de passe (8 caractères minimum), numéro de téléphone
3. Un code de vérification à 6 chiffres s'affiche directement sur la page *(mode démo — en production il serait envoyé par SMS)*
4. Saisir le code pour activer le compte
5. Se connecter avec ses identifiants

### Se connecter / Se déconnecter

- **Connexion** : e-mail + mot de passe via le formulaire de login
- **Déconnexion** : lien *Se déconnecter* dans la navigation
- **Mot de passe oublié** : lien sur la page de connexion → saisir son e-mail → code OTP affiché → choisir un nouveau mot de passe

### Consulter le catalogue

- La page `/vehicles` liste tous les véhicules disponibles
- Filtres disponibles : recherche par marque/modèle, type (vente / location)
- Cliquer sur un véhicule pour accéder à sa fiche détaillée (caractéristiques, prix, photos)

### Mettre un véhicule en favori

- Sur la fiche d'un véhicule, cliquer sur **Ajouter aux favoris**
- Retrouver ses favoris via le menu **Mes favoris**
- Cliquer à nouveau sur le bouton pour retirer le véhicule des favoris

### Ouvrir un dossier (achat ou location)

1. Sur la fiche d'un véhicule, cliquer sur **Ouvrir un dossier**
2. Le dossier est créé avec le statut *En attente*
3. Accéder au dossier via **Mon dossier** dans la navigation
4. Déposer les documents demandés (CNI, justificatif de domicile, etc.) en les téléversant un par un
5. Suivre l'avancement du dossier depuis la même page

### Gérer son profil

- Accessible via **Mon profil** dans la navigation
- Modifier ses informations personnelles (prénom, nom, e-mail, téléphone, adresse)
- Changer son mot de passe
- Supprimer son compte

---

## Espace administrateur

### Accès

- URL : `/admin/login`
- Identifiants fournis séparément par l'administrateur principal

### Catalogue véhicules

| Action | Description |
|---|---|
| Lister | Vue d'ensemble avec filtres (statut, tri) |
| Créer | Formulaire complet : VIN, immatriculation, marque, modèle, année, carburant, transmission, kilométrage, prix |
| Modifier | Édition de toutes les informations d'un véhicule |
| Activer | Rendre un véhicule visible dans le catalogue public |
| Désactiver | Retirer un véhicule du catalogue (avec motif) |

### Dossiers clients

- Liste de tous les dossiers avec filtres (type, statut, tri)
- Accès au détail d'un dossier : informations client, véhicule concerné, documents déposés
- **Changer le statut** d'un dossier : *En attente → En cours → Approuvé / Refusé / Annulé*
- **Gérer les documents** :
  - Verrouiller / déverrouiller un document (empêche le client de le remplacer)
  - Valider ou refuser un document (avec motif de refus)
  - Visualiser un document dans le navigateur
- **Supprimer un dossier** (envoi en corbeille)

### Corbeille

- Liste des dossiers supprimés
- **Restaurer** un dossier (le remet dans l'état précédent la suppression)
- **Supprimer définitivement** un dossier

### Mon profil admin

- Modifier ses informations personnelles (prénom, nom, e-mail)
- Changer son mot de passe

---

## Rôles et permissions

| Fonctionnalité                  | Visiteur | Client connecté | Administrateur |
|:--------------------------------|:--------:|:---------------:|:--------------:|
| Consulter le catalogue          |    ✓     |        ✓        |       ✓        |
| Créer un compte                 |    ✓     |        —        |       —        |
| Gérer ses favoris               |    —     |        ✓        |       —        |
| Ouvrir / suivre un dossier      |    —     |        ✓        |       —        |
| Gérer son profil                |    —     |        ✓        |       ✓        |
| Gérer le catalogue              |    —     |        —        |       ✓        |
| Gérer les dossiers clients      |    —     |        —        |       ✓        |
| Accéder à la corbeille          |    —     |        —        |       ✓        |

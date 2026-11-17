# AGENTS.md — CYBER OPS / Cyber Crisis Room

## 1. Mission du projet

Tu interviens sur le projet **CYBER OPS — Cyber Crisis Room**.

Il s'agit d'une application web de simulation de crise cyber destinée à des démonstrations pédagogiques, des exercices de sensibilisation et la présentation des mécanismes de gestion d'un incident de cybersécurité.

L'application simule une cyberattaque affectant progressivement un système d'information industriel.

Elle permet de visualiser :
- Le renseignement sur les menaces (Threat Intelligence).
- La supervision des événements de sécurité (SOC Monitoring).
- La visualisation cartographique des cybermenaces (Global Threat Map).
- Le pilotage d'une cellule de crise (Crisis Management).
- Les décisions opérationnelles et leurs conséquences simulées.

**Ce projet n'est pas un véritable SOC et ne doit pas être présenté comme tel.**

Les événements, les systèmes, les organisations et les impacts métier sont fictifs.

---

## 2. Règles générales de développement

Avant toute modification :

1. Comprendre l'architecture existante.
2. Identifier les interactions entre le frontend et le backend.
3. Vérifier les contrats des API existantes.
4. Préserver les fonctionnalités déjà opérationnelles.
5. Éviter les réécritures inutiles.
6. Tester les modifications après leur implémentation.

### Principes importants

- Ne pas supprimer une fonctionnalité existante sans demande explicite.
- Ne pas modifier arbitrairement les noms des endpoints API.
- Ne pas inventer de données ou de statistiques présentées comme réelles.
- Ne pas introduire de dépendances lourdes sans justification.
- Préférer une architecture simple, lisible et maintenable.
- Privilégier les modifications cohérentes plutôt que les corrections ponctuelles accumulées.
- Lorsqu'une modification concerne plusieurs écrans, conserver une identité graphique commune.
- Ne jamais casser le scénario de simulation existant pour améliorer l'interface.

En cas de doute sur une règle métier, examiner `app/main.py` avant de modifier le frontend.

---

## 3. Environnement technique

### Backend

- Python 3
- FastAPI
- Uvicorn
- API REST
- État de simulation géré côté serveur

### Frontend

- HTML5
- CSS3
- JavaScript natif
- Appels HTTP avec Fetch API
- Rendu dynamique des données JSON

### Environnement de développement

- Kali Linux
- Visual Studio Code
- Environnement virtuel Python
- Port HTTP 8090

Ne pas introduire de framework frontend (React, Vue, Angular, etc.) sans demande explicite.

---

## 4. Structure du projet

Architecture actuelle :

```text
cyber-crisis-room/
│
├── AGENTS.md
├── README.md
│
├── app/
│   ├── main.py
│   │
│   └── static/
│       ├── index.html
│       ├── crisis.html
│       └── map.html
│
└── .venv/
```

### Responsabilités des fichiers

#### `app/main.py`

Backend FastAPI.

Il gère :
- Le moteur de simulation.
- Les événements du scénario.
- L'état global de la simulation.
- Le démarrage et l'arrêt du scénario.
- Les impacts métier.
- Les décisions de la cellule de crise.
- Les endpoints REST.

Ce fichier constitue la référence pour les règles métier.

#### `app/static/index.html`

Interface principale.

Elle regroupe deux vues :
- Threat Intelligence.
- SOC Monitoring.

Le rendu dépend de la route demandée.

Elle contient :
- Le menu latéral.
- L'en-tête applicatif.
- Les composants visuels.
- Les tableaux de bord.
- Les événements de sécurité.
- Les appels API.
- Le rafraîchissement périodique des données.

#### `app/static/crisis.html`

Interface Crisis Management.

Elle contient :
- Le niveau de crise.
- Les indicateurs opérationnels.
- Les impacts métier.
- Les actions de la cellule de crise.
- Le journal des décisions.

Elle utilise les mêmes API que l'interface principale.

#### `app/static/map.html`

Interface cartographique indépendante.

Elle permet de visualiser les cybermenaces sur une carte.

Elle est accessible depuis le menu latéral.

---

## 5. Identité graphique et interface utilisateur

L'application doit conserver une identité visuelle homogène sur tous les écrans.

### Direction artistique

Style :
- SOC professionnel.
- Interface sombre.
- Inspiration centre opérationnel de cybersécurité.
- Présentation dense mais lisible.
- Informations structurées en panneaux.
- Couleurs utilisées pour représenter les niveaux de gravité et les états opérationnels.

### Palette principale

```css
--bg:#080e19;
--sidebar:#0b1422;
--panel:#111c2c;
--panel2:#14243a;
--border:#26364b;
--text:#e5edf7;
--muted:#8799b1;
--cyan:#38bdf8;
--red:#ef4444;
--orange:#f59e0b;
--green:#22c55e;
--purple:#a78bfa;
```

### Menu latéral de référence

Le menu de `index.html` constitue la référence graphique et structurelle.

Il doit être reproduit à l'identique dans `crisis.html`.

Structure actuelle :

```text
◆ CYBER OPS

MONITORING

◈  Threat Intelligence       01
◎  Carte mondiale            02
▦  SOC Monitoring            03

GESTION DE CRISE

⚑  Crisis Management         04

----------------------------

● SYSTEM ONLINE
   CYBER OPS · VERSION 1.0
```

### Règles du menu

- Largeur desktop : 250 px.
- Largeur intermédiaire : 215 px.
- Largeur réduite : 65 px.
- En-tête du logo : 76 px.
- Même typographie.
- Même espacement.
- Mêmes icônes.
- Mêmes couleurs.
- Même comportement responsive.
- Même structure HTML et CSS autant que possible.

L'élément correspondant à la page courante doit être marqué `active`.

Ne jamais créer une variante visuellement différente du menu dans une nouvelle page.

### Navigation

| Vue | URL | Fichier |
|---|---|---|
| Threat Intelligence | `/screen/threats` | `index.html` |
| Carte mondiale | `/static/map.html` | `map.html` |
| SOC Monitoring | `/screen/soc` | `index.html` |
| Crisis Management | `/screen/crisis` | `crisis.html` |

Attention : la carte est une page indépendante et non une vue de `index.html`.

---

## 6. Fonctionnement du moteur de simulation

Le scénario actuel comporte six événements successifs.

Le délai nominal entre les événements est de huit secondes.

### Scénario actuel

| Étape | Système | Gravité | Événement | MITRE ATT&CK |
|---|---|---|---|---|
| 1 | AD-DC01 | CRITICAL | Compromission d'un compte administrateur | T1078 |
| 2 | WS-FINANCE-04 | HIGH | PowerShell suspect | T1059.001 |
| 3 | SRV-FILE01 | HIGH | Mouvement latéral SMB | T1021.002 |
| 4 | SRV-ERP01 | CRITICAL | Suspicion d'exfiltration | T1041 |
| 5 | SRV-FILE02 | CRITICAL | Chiffrement de fichiers | T1486 |
| 6 | SOC | CRITICAL | Activation de la cellule de crise | IR |

### Progression

Le scénario représente une attaque de type ransomware avec :
- Compromission initiale.
- Exécution de commandes.
- Mouvement latéral.
- Exfiltration suspectée.
- Chiffrement.
- Activation de la réponse à incident.

Ne pas modifier l'ordre des événements ou leurs identifiants MITRE ATT&CK sans demande explicite.

---

## 7. État métier et décisions

Le backend maintient notamment les informations suivantes :

- `status`
- `running`
- `paused`
- `completed`
- `start_time`
- `current_step`
- `scenario_total`
- `events`
- `response_actions`
- `impacts`
- `decisions`
- `crisis_level`
- `total`
- `critical`
- `systems`
- `last_event`

### Source de vérité

Le backend est la source de vérité.

Le frontend ne doit pas maintenir un état métier indépendant qui pourrait diverger de l'état du serveur.

Les vues doivent être actualisées à partir des données retournées par `/api/state`.

### Actions de réponse à incident

Le dictionnaire `response_actions` constitue la référence des décisions :

```python
{
    "admin_disabled": False,
    "network_isolated": False,
    "pca_activated": False,
    "authorities_notified": False,
    "backup_restore_started": False
}
```

### Identifiants des décisions

Les identifiants actuellement utilisés par le frontend sont :

| Action | Identifiant API |
|---|---|
| Désactiver le compte administrateur | `disable_admin` |
| Isoler le réseau | `isolate_network` |
| Activer le PCA | `activate_pca` |
| Préparer la notification | `notify_authorities` |
| Restaurer les sauvegardes | `restore_backup` |

Ne pas confondre les identifiants des actions API et les noms des indicateurs dans `response_actions`.

### Conséquences métier importantes

L'isolement réseau :
- Empêche la poursuite de l'exfiltration dans le scénario.
- Ne permet pas d'annuler un chiffrement déjà réalisé.

L'activation du PCA :
- Permet de représenter une continuité d'activité en mode dégradé.

La restauration :
- Représente le lancement d'une procédure de restauration.
- Ne doit pas être présentée comme une restauration effectivement terminée sans implémentation correspondante.

Les actions sont des décisions simulées. Elles ne doivent jamais exécuter de véritables opérations sur un système d'information.

---

## 8. API REST

Les endpoints existants sont :

| Méthode | Endpoint | Fonction |
|---|---|---|
| GET | `/api/state` | État global |
| POST | `/api/start` | Démarrer le scénario |
| POST | `/api/pause` | Mettre en pause |
| POST | `/api/resume` | Reprendre |
| POST | `/api/reset` | Réinitialiser |
| POST | `/api/decisions` | Enregistrer une décision |

### Exemple de décision

```json
{
  "action": "isolate_network",
  "actor": "Cellule de crise"
}
```

Le backend doit retourner un résultat permettant au frontend de vérifier que la décision a bien été enregistrée.

Ne pas modifier le format des requêtes ou des réponses sans mettre à jour tous les consommateurs.

---

## 9. Rafraîchissement des interfaces

Les interfaces récupèrent périodiquement l'état de la simulation.

L'endpoint utilisé est :

```text
GET /api/state
```

La fréquence actuellement utilisée est de l'ordre d'une seconde à 1,5 seconde selon la vue.

Lors d'une évolution :
- Éviter les appels inutiles.
- Gérer les erreurs réseau.
- Ne pas perdre les décisions déjà enregistrées.
- Éviter de reconstruire inutilement toute la page.
- Préserver une bonne lisibilité pendant la simulation.

---

## 10. Threat Intelligence et carte mondiale

La vue Threat Intelligence présente des informations sur les menaces et les techniques d'attaque.

Les sources envisagées comprennent :
- CERT-FR / ANSSI.
- ThreatFox.
- URLhaus.
- CISA Known Exploited Vulnerabilities.

Les sources non connectées doivent rester explicitement identifiées comme telles.

Ne jamais afficher de faux flux temps réel, de faux IOC ou de faux nombres d'attaques comme s'ils provenaient de sources externes.

### Géolocalisation

Les événements actuels ne fournissent pas de géolocalisation fiable de l'origine des attaquants.

Ne pas attribuer artificiellement une origine géographique aux attaques.

La carte peut afficher des données de démonstration, mais celles-ci doivent être clairement identifiées comme simulées.

---

## 11. Commandes de développement

### Démarrer le projet

```bash
cd ~/Work/cyber-crisis-room

source .venv/bin/activate

uvicorn app.main:app --host 0.0.0.0 --port 8090 --reload
```

### Tester l'API

```bash
curl -s http://localhost:8090/api/state | python -m json.tool
```

### Démarrer la simulation

```bash
curl -X POST http://localhost:8090/api/start
```

### Mettre en pause

```bash
curl -X POST http://localhost:8090/api/pause
```

### Reprendre

```bash
curl -X POST http://localhost:8090/api/resume
```

### Réinitialiser

```bash
curl -X POST http://localhost:8090/api/reset
```

### Accéder aux interfaces

```text
http://localhost:8090/screen/threats
http://localhost:8090/screen/soc
http://localhost:8090/screen/crisis
http://localhost:8090/static/map.html
```

---

## 12. Tests à effectuer après modification

Après chaque évolution importante, vérifier :

### Backend
- Le serveur démarre sans erreur.
- Les endpoints répondent.
- Le scénario démarre.
- Le scénario peut être mis en pause et repris.
- La réinitialisation fonctionne.
- Les décisions sont enregistrées.

### Frontend
- Les quatre vues sont accessibles.
- Le menu est identique sur les pages applicatives.
- Le bon élément du menu est actif.
- Les données se rafraîchissent.
- Les erreurs réseau sont gérées.
- La carte est accessible.
- L'affichage reste correct sur différentes tailles d'écran.

### Cohérence métier
- Les événements sont dans le bon ordre.
- Les niveaux de gravité sont cohérents.
- Les impacts métier correspondent au scénario.
- Les décisions ont les conséquences attendues.
- Les données affichées correspondent à l'état du backend.

---

## 13. Priorités d'évolution

Les évolutions doivent privilégier les objectifs suivants :

1. Améliorer le réalisme de la simulation.
2. Renforcer la cohérence entre SOC et cellule de crise.
3. Améliorer la visualisation des impacts métier.
4. Enrichir les interactions de la cellule de crise.
5. Améliorer la lisibilité des tableaux de bord.
6. Ajouter des scénarios configurables.
7. Préparer des démonstrations reproductibles.

La qualité de la démonstration et la cohérence du scénario sont prioritaires sur l'ajout de fonctionnalités décoratives.

---

## 14. Consignes à l'agent de développement

Tu agis comme un développeur senior spécialisé dans les applications de cybersécurité et les outils SOC.

Pour chaque demande :

1. Analyse le code existant avant d'intervenir.
2. Identifie les fichiers concernés.
3. Vérifie les dépendances fonctionnelles.
4. Propose une solution cohérente avec l'architecture actuelle.
5. Préserve les fonctionnalités existantes.
6. Effectue les modifications.
7. Vérifie la syntaxe et le fonctionnement.
8. Fournis un résumé des modifications.
9. Signale clairement les fonctionnalités non testées.

Lorsque l'utilisateur demande un fichier complet, fournis le fichier complet plutôt que des fragments à assembler.

Ne prétends jamais qu'une fonctionnalité est opérationnelle si elle n'a pas été vérifiée.

**Principe directeur : faire évoluer CYBER OPS comme une application SOC cohérente, réaliste et professionnelle, sans perdre sa simplicité de déploiement et de démonstration.**
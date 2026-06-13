# Méthode TRACE

Définition de scénarios d'attaque centrés sur la donnée, pour l'entraînement
des équipes red et purple.

## 1. Objet

Les référentiels d'attaque classiques (Cyber Kill Chain, MITRE ATT&CK)
décrivent une attaque par les **techniques** employées par l'adversaire
(« comment il agit »). Cette approche est précieuse pour la détection, mais
elle est peu adaptée à l'entraînement sur la **phase amont** d'une attaque
ciblée : la construction progressive d'une connaissance de la cible humaine.

La méthode TRACE propose une taxonomie **autonome et centrée sur la donnée**.
Elle ne décrit pas la technique, mais le **signal exploité** sur la personne
visée et le chemin qui transforme une trace anodine en cible exploitable. Elle
sert à *définir*, *noter* et *graduer* des scénarios d'attaque reproductibles
pour des exercices red et purple.

Le postulat fondateur est le suivant : une attaque ciblée n'est jamais un acte
isolé, c'est l'**exploitation d'une chaîne de signaux**. Le danger ne vient pas
d'une donnée isolée mais de son recoupement. La méthode rend cette chaîne
explicite et manipulable.

## 2. Le modèle TRACE

Tout scénario se définit le long de cinq axes. Chaque axe possède un
vocabulaire contrôlé : l'auteur du scénario choisit une valeur par axe.

| Axe | Nom | Question à laquelle il répond |
| --- | --- | --- |
| T | Trace | Quel signal sur la cible est exploité ? |
| R | Recueil | Comment l'adversaire l'obtient-il ? |
| A | Attribut | Quel élément cherche-t-il à établir ? |
| C | Corrélation | Quel niveau d'identification atteint-il ? |
| E | Exploitation | Que fait-il du profil obtenu ? |

L'enchaînement `T + R` décrit l'**acquisition**, `A` décrit l'**intention**,
`C` mesure la **maturité du profil**, et `E` décrit le **passage à l'acte**.

### 2.1. Axe T — Trace exploitée

La nature du signal capté sur la personne.

| Code | Surface de donnée | Exemples |
| --- | --- | --- |
| T1 | Trace déclarative publique | posts, CV en ligne, avis, photos |
| T2 | Empreinte technique | fingerprint navigateur/appareil, cookies, IP |
| T3 | Métadonnée | EXIF/GPS d'une photo, horodatage, métadonnées de fichier |
| T4 | Donnée de fuite | identifiants issus d'une violation de données |
| T5 | Donnée enrichie | segment de courtier en données, donnée commerciale |
| T6 | Attribut inféré | trait psychométrique ou attribut sensible déduit |
| T7 | Trace relationnelle | graphe social, entourage, fournisseurs |

### 2.2. Axe R — Recueil

Le mode d'acquisition du signal.

| Code | Mode | Description |
| --- | --- | --- |
| R1 | Collecte passive | observation et scraping de sources ouvertes |
| R2 | Collecte active | interaction provoquée, compte-leurre, balise |
| R3 | Acquisition marchande | achat auprès d'un courtier ou d'une place de marché |
| R4 | Acquisition par fuite | exploitation d'une violation (simulée en exercice) |
| R5 | Agrégation | recoupement et corrélation de plusieurs sources |

### 2.3. Axe A — Attribut visé

L'objectif de profilage, c'est-à-dire ce que l'adversaire cherche à établir.

| Code | Attribut | Finalité offensive typique |
| --- | --- | --- |
| A1 | Identité civile | nom, adresse, employeur, fonction |
| A2 | Localisation et routine | déplacements, habitudes, présence |
| A3 | Surface technique | appareils, comptes, services, mots de passe réutilisés |
| A4 | Profil psychologique | traits, biais cognitifs, leviers de persuasion |
| A5 | Attribut sensible inféré | santé, opinions, orientation, situation |
| A6 | Cercle de confiance | hiérarchie, proches, prestataires |
| A7 | Pouvoir et accès | rôle, droits dans le système d'information |

### 2.4. Axe C — Corrélation

Le niveau d'identification atteint. Cet axe est une **échelle de maturité** : un
scénario réaliste décrit souvent une montée de C0 vers C4.

| Code | Niveau | État du profil |
| --- | --- | --- |
| C0 | Anonyme | signal capté mais non rattaché à une personne |
| C1 | Pseudonyme | identifiant persistant sans identité civile |
| C2 | Identifié | résolution d'identité réussie |
| C3 | Enrichi | profil consolidé à partir de plusieurs sources |
| C4 | Segmenté | cible priorisée, scorée et prête à l'exploitation |

### 2.5. Axe E — Exploitation

Le passage à l'acte. Il combine un **vecteur** et un **effet recherché**.

| Vecteurs courants | Effets recherchés |
| --- | --- |
| hameçonnage ciblé, hameçonnage vocal | accès initial |
| usurpation d'identité, fraude au président | compromission de compte |
| échange de carte SIM, bourrage d'identifiants | fraude financière |
| ingénierie sociale physique, talonnage | intrusion physique |
| extorsion, manipulation d'influence ciblée | atteinte à la réputation, désinformation |

## 3. Notation d'un scénario

Un scénario se résume par une **signature TRACE** compacte :

```text
[T] + [R] -> A[x] @ C[x] => E[vecteur:effet]
```

Exemple de signature :

```text
T3 + R1 -> A2 @ C2 => E[filature:intrusion physique]
```

Lecture : une métadonnée de géolocalisation (T3), collectée passivement (R1),
sert à établir la routine de déplacement (A2) d'une personne désormais
identifiée (C2), en vue d'une intrusion physique préparée par filature.

Un scénario complexe se note comme une **chaîne** d'étapes, chaque étape faisant
progresser l'axe C :

```text
T1+R1 -> A1 @ C2  ->  T4+R5 -> A3 @ C3  ->  T6+R5 -> A4 @ C4  =>  E[hameçonnage ciblé:accès initial]
```

## 4. Graduation pour l'entraînement

Chaque scénario reçoit une cotation sur quatre critères, notés de 1 à 3, puis
un **palier de difficulté** global de 1 à 5.

| Critère | 1 | 2 | 3 |
| --- | --- | --- | --- |
| Réalisme | hypothétique | plausible | observé dans la réalité |
| Effort adverse | faible | moyen | élevé |
| OPSEC requis | faible | moyen | élevé |
| Détectabilité défensive | élevée | moyenne | faible |

Le palier global oriente l'usage pédagogique.

| Palier | Profil de joueur | Usage |
| --- | --- | --- |
| 1 | sensibilisation | démonstration d'exposition personnelle |
| 2 | red junior | exercice guidé sur une seule source |
| 3 | red confirmé | chaîne multi-sources sur persona fictif |
| 4 | purple | exercice conjoint avec objectifs de détection |
| 5 | red senior, cyber-range | campagne complète sous contrainte OPSEC |

## 5. Volet purple — correspondance défensive par axe

Pour les exercices purple, chaque valeur de l'axe T se relie à des signaux de
détection et à des contre-mesures, afin que l'équipe bleue ait des objectifs
mesurables face à chaque étape rouge.

| Axe T | Signaux de détection côté défense | Contre-mesures |
| --- | --- | --- |
| T1 déclaratif | mentions de marque, veille e-réputation | politique de publication, cloisonnement des comptes |
| T2 empreinte | balises de suivi, scripts de fingerprint | anti-pistage, navigateurs durcis, réseau d'entreprise |
| T3 métadonnée | fuite de fichiers riches en métadonnées | nettoyage EXIF, prévention de fuite de données |
| T4 fuite | apparition d'identifiants dans des dumps | surveillance de fuites, authentification forte, rotation |
| T5 enrichie | sollicitations issues de segments | droits d'opposition et d'effacement, registre des courtiers |
| T6 inféré | ciblage anormalement précis | minimisation des signaux exposés |
| T7 relationnel | reconnaissance de l'entourage | sensibilisation de l'écosystème, segmentation des accès |

Un exercice purple complet associe à chaque étape de la signature TRACE rouge un
objectif bleu : *détecter*, *retarder* ou *attribuer* l'étape correspondante.

## 6. Mode d'emploi

Construction d'un scénario d'entraînement en six temps.

1. Définir un **persona fictif** complet et documenté, jamais une personne
   réelle.
2. Fixer l'**objectif final** du scénario, c'est-à-dire la valeur de l'axe E.
3. Remonter la chaîne : déterminer le niveau C nécessaire, puis l'attribut A,
   puis les couples T plus R qui permettent d'y parvenir.
4. Écrire la **signature TRACE** complète, étape par étape.
5. Coter le scénario et fixer son palier.
6. Pour un exercice purple, associer les objectifs défensifs de la section 5.

Le gabarit prêt à remplir se trouve dans `gabarit-scenario.md`.

## 7. Cadre éthique et légal

Cette méthode est un outil d'**entraînement défensif**. Son usage est
strictement encadré.

- Travailler exclusivement sur des **personas fictifs** et des données
  synthétiques. Ne jamais profiler une personne réelle hors périmètre
  d'engagement autorisé et écrit.
- Le profilage d'une personne identifiable relève du RGPD même à partir de
  sources publiques : la disponibilité publique n'autorise pas un usage libre.
- Les étapes de type R4 (fuite) sont **simulées** en environnement cloisonné,
  jamais reproduites sur des données réelles compromises.
- Tout exercice mobilisant des cibles réelles requiert un mandat explicite,
  une autorisation écrite et un périmètre défini, conformément aux règles
  d'engagement de l'organisation.

## 8. Positionnement par rapport aux référentiels existants

La méthode TRACE est autonome, mais elle s'articule sans friction avec les
référentiels techniques. À titre indicatif, les axes T, R, A et C couvrent en
profondeur la phase de reconnaissance que les autres cadres résument en une
seule étape, tandis que l'axe E sert de point de jonction vers la suite d'une
chaîne d'attaque décrite, elle, par les techniques.

| Étape TRACE | Recouvrement indicatif |
| --- | --- |
| T, R, A, C | phase de reconnaissance amont d'une attaque ciblée |
| E | accès initial et bascule vers l'exploitation technique |

Cette articulation permet d'enchaîner un exercice TRACE sur la reconnaissance
avec un exercice technique sur la suite de la chaîne, sans rupture.

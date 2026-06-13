# Gabarit de scénario TRACE

Fiche réutilisable pour définir un scénario d'attaque destiné à l'entraînement
red ou purple. Dupliquer ce gabarit pour chaque nouveau scénario. Se reporter à
`methode-trace.md` pour le vocabulaire des axes.

## Identification

| Champ | Valeur |
| --- | --- |
| Titre du scénario | _à remplir_ |
| Auteur | _à remplir_ |
| Date | _à remplir_ |
| Public visé | red junior / red confirmé / purple / cyber-range |
| Persona fictif | _nom et description de la cible synthétique_ |

## Signature TRACE

```text
[T] + [R] -> A[x] @ C[x] => E[vecteur:effet]
```

## Déroulé par étapes

| Étape | T | R | A | C atteint | Action concrète |
| --- | --- | --- | --- | --- | --- |
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| ... | | | | | |

## Cotation

| Critère | Note (1-3) | Justification |
| --- | --- | --- |
| Réalisme | | |
| Effort adverse | | |
| OPSEC requis | | |
| Détectabilité défensive | | |
| **Palier global (1-5)** | | |

## Objectifs purple

| Étape rouge | Objectif bleu | Signal de détection attendu | Contre-mesure évaluée |
| --- | --- | --- | --- |
| 1 | détecter / retarder / attribuer | | |
| 2 | | | |

## Critères de réussite

- Condition de succès côté red : _à remplir_
- Condition de succès côté blue : _à remplir_
- Données et environnement autorisés : _à remplir_

## Garde-fous

- [ ] Persona entièrement fictif, aucune personne réelle ciblée
- [ ] Étapes de fuite simulées en environnement cloisonné
- [ ] Mandat et règles d'engagement validés si cible réelle
- [ ] Données détruites en fin d'exercice

---

## Exemple rempli

Scénario illustratif fondé sur un persona fictif.

### Identification de l'exemple

| Champ | Valeur |
| --- | --- |
| Titre du scénario | Du selfie de course au courriel piégé |
| Public visé | red confirmé puis purple |
| Persona fictif | « Camille Martin », cadre fictive d'une entreprise fictive |

### Signature TRACE de l'exemple

```text
T1+R1 -> A1 @ C2  ->  T3+R5 -> A2 @ C3  ->  T6+R5 -> A4 @ C4  =>  E[hameçonnage ciblé:accès initial]
```

### Déroulé de l'exemple

| Étape | T | R | A | C atteint | Action concrète |
| --- | --- | --- | --- | --- | --- |
| 1 | T1 | R1 | A1 | C2 | un profil public lie pseudonyme, employeur et fonction |
| 2 | T3 | R5 | A2 | C3 | les métadonnées de photos de course révèlent la routine |
| 3 | T6 | R5 | A4 | C4 | l'agrégat permet d'inférer un levier de persuasion |
| 4 | — | — | — | C4 | envoi d'un courriel piégé contextualisé pour l'accès initial |

### Cotation de l'exemple

| Critère | Note (1-3) | Justification |
| --- | --- | --- |
| Réalisme | 3 | chaîne observée dans des cas réels documentés |
| Effort adverse | 2 | sources ouvertes, recoupement manuel modéré |
| OPSEC requis | 2 | collecte passive, faible exposition |
| Détectabilité défensive | 2 | détectable au stade du courriel piégé |
| **Palier global** | 3 | chaîne multi-sources sur persona fictif |

### Objectifs purple de l'exemple

| Étape rouge | Objectif bleu | Signal de détection attendu | Contre-mesure évaluée |
| --- | --- | --- | --- |
| 2 | retarder | fuite de photos riches en métadonnées | nettoyage EXIF, sensibilisation |
| 4 | détecter | courriel ciblé incohérent | filtrage, signalement, double facteur |

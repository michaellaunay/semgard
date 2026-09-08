# ADR-001 — Adopter MorphoRepr comme notation d'étiquettes, avec un profil fermé et un parseur paramétré

**Statut** : accepté — 2026-09-08

## Contexte

SemGard doit sérialiser, pour chaque segment de texte, un tuple d'étiquettes sémantiques
(forme, destinataire, polarité, sujet, causation, acte) de façon à ce que des expressions
régulières ordinaires puissent s'y appliquer. Le projet MorphoRepr (Launay, 2026 ; v0.30)
définit une grammaire agglutinante `(préfixe)* racine (infixe)* suffixe` et un parseur par
segmentation sur tirets, mais avec un inventaire codé en dur (profil SAE, préfixes fermés
`mal-`, `ne-`, `pli-`, `plej-`, `duon-`).

## Décision

1. Les étiquettes SemGard sont des **expressions MorphoRepr** d'un profil dédié `semgard`.
2. Le profil est **fermé** (16 morphèmes, pas de racines libres) et **ASCII strict**.
3. Les préfixes sont répartis en **classes ordonnées** (`forme < destinataire < polarité`) ;
   c'est la seule extension de la grammaire, et elle rend les regex stables.
4. Le parseur est **paramétré par un objet `Inventory`** ; SemGard en porte une implémentation
   compatible (`semgard/parser.py`) testée sur les formes du papier, destinée à être remplacée
   par `morphorepr.utils.morphorepr_parser` une fois celui-ci paramétré (contribution amont).
5. L'espéranto n'est qu'un **métalangage** : aucun modèle ne voit d'espéranto en entrée.

## Alternatives écartées

- *Tuples verbeux* (`DIRECTIVE[addressee=AI, topic=rules]`) : lisibles mais irréguliers, mauvais
  support regex, pas de mutualisation avec MorphoRepr. Conservés comme syntaxe de surface
  bijective à venir (spec §2.5).
- *Encoder le destinataire comme terme additif* (`0.83·mal-regul-u + 0.90·ai-o`) : parseable avec
  la grammaire actuelle, mais la regex par terme perd l'information de destinataire.
- *Réécrire un parseur sans lien avec MorphoRepr* : perd la compatibilité et l'argument
  « deux canaux, une notation » (spec §8).

## Conséquences

- Deux contributions amont sont nécessaires et utiles au papier : `Inventory` dans le parseur,
  classifieur `directive_mood` (contrepartie du suffixe `-u`, absente des propriétés robustes).
- Tout changement d'inventaire est une nouvelle version de lexique et de corpus.
- L'ordre agglutinant est un pari ergonomique ; l'ablation « sac de morphèmes » (spec §6) le teste.

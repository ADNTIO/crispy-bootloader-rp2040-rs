# Analyse : portage RP2350 + signature du firmware

> Document d'analyse technique et d'estimation de charge.
> Cible : faire évoluer le bootloader A/B (actuellement RP2040) vers le RP2350,
> et remplacer/compléter le contrôle d'intégrité actuel (CRC32) par une
> **signature cryptographique** du firmware.

## 1. Rappel de l'architecture actuelle

Bootloader A/B en Rust `no_std` qui :

1. S'exécute depuis la flash XIP (`0x1000_0000`), précédé d'un `boot2` RP2040
   (`rp2040_boot2::BOOT_LOADER_GENERIC_03H`, section `.boot2`).
2. Lit `BootData` (métadonnées de boot, 32 octets `repr(C)`) en flash à
   `0x1019_0000`.
3. Choisit une banque (A `0x1001_0000` / B `0x100D_0000`, 768 KB chacune),
   gère le rollback automatique (3 tentatives), valide via **CRC32 + plage de
   la table de vecteurs**.
4. **Copie** le firmware de la flash vers la RAM (`0x2000_0000`, 192 KB) et
   saute dessus (firmware exécuté en RAM).
5. En mode update (déclenché par GP2 bas ou un magic en RAM), expose un
   **USB CDC** et un protocole `postcard` (StartUpdate / DataBlock / FinishUpdate
   / SetActiveBank / WipeAll / Reboot). Les blocs sont bufferisés en RAM puis
   écrits en flash, avec double vérification CRC (RAM puis flash).

Composants :

| Crate / dossier | Rôle | Spécifique RP2040 ? |
|---|---|---|
| `crispy-bootloader` | Bootloader (binaire embarqué) | **Oui, fortement** |
| `crispy-common-rs` | Protocole + utilitaires flash partagés | Partiellement (feature `embedded`) |
| `crispy-fw-sample-rs` | Firmware d'exemple (Rust, exécution RAM) | **Oui** |
| `crispy-fw-sample-cpp` | Firmware d'exemple (Pico SDK C++) | **Oui** |
| `crispy-sdk-cpp` | SDK C++ (boot_data, commandes, linker) | **Oui** |
| `crispy-upload-rs` | CLI hôte (upload/status/bank/bin2uf2) | Non (std) — sauf family-id UF2 |
| `crispy-upload-python` / `crispy-common-python` | CLI + protocole Python | Non |
| `linker_scripts/` | `bootloader_rp2040.x`, `fw_rp2040.x` | **Oui** |

Le contrôle d'intégrité actuel repose **uniquement sur CRC32 (ISO-HDLC)** :
c'est une protection contre la corruption, **pas** une protection
cryptographique (aucune authentification de l'origine ; trivial à forger).

---

## 2. Portage RP2040 → RP2350

### 2.1 Différences matérielles structurantes

| Sujet | RP2040 | RP2350 | Impact |
|---|---|---|---|
| Cœurs | 2× Cortex-M0+ (Armv6-M) | 2× Cortex-M33 (Armv8-M) **ou** 2× Hazard3 (RISC-V) | Cible Rust, NVIC, sécurité |
| Cible Rust | `thumbv6m-none-eabi` | `thumbv8m.main-none-eabihf` | toolchain, `.cargo/config` |
| HAL rp-rs | `rp2040-hal` 0.11 | **`rp235x-hal`** | API peripherals/clocks/usb/flash |
| 2e étage de boot | `boot2` 256 o (`rp2040-boot2`) | **Bloc IMAGE_DEF** (`.start_block`) validé par le bootrom | Linker + `main.rs` |
| SRAM | 264 KB | **520 KB** | Linker (banque RAM, buffer upload plus grands) |
| ROM bootrom | table à `0x14/0x18`, lookup maison | Table/ABI différentes (drapeaux Arm/RISC-V/Secure) | Réécriture de `flash.rs` |
| NVIC | 32 lignes (1 registre) | jusqu'à ~52 lignes (plusieurs registres) | `prepare_for_firmware_handoff` |
| Sécurité | aucune | **TrustZone-M (Secure/Non-secure), OTP, secure boot bootrom (ECDSA secp256k1)** | cf. §3 option B |
| Accél. crypto | aucune | **bloc SHA-256 matériel** | accélère la signature (cf. §3) |
| UF2 family-id | `0xe48bff56` | ARM-S `0xe48bff59` (RISC-V `…5a`, ARM-NS `…5b`) | `bin2uf2`, Makefile |
| probe-rs chip | `RP2040` | `RP2350` | `.cargo/config`, Makefile |

### 2.2 Impact fichier par fichier

| Fichier | Modif. nécessaire | Difficulté |
|---|---|---|
| `Cargo.toml` (workspace) + crates embarquées | `rp2040-hal`/`rp2040-boot2` → `rp235x-hal` ; retrait de `rp2040-boot2` | Faible |
| `.cargo/config.toml` | cible `thumbv8m.main-none-eabihf`, `--chip RP2350` | Faible |
| `Makefile` | `EMBEDDED_TARGET`, `CHIP`, family-id UF2, adresses | Faible |
| `linker_scripts/bootloader_rp2040.x` → `…_rp2350.x` | Section `.start_block` (IMAGE_DEF) au lieu de `.boot2` ; refonte de la carte RAM (520 KB) ; recalcul des symboles `__fw_*` | **Élevée** (réglages + tests HW) |
| `linker_scripts/fw_rp2040.x` → `…_rp2350.x` | Idem (firmware exécuté en RAM, plus de RAM dispo) | Moyenne |
| `crispy-bootloader/src/main.rs` | Remplacer `static BOOT2` par `#[link_section=".start_block"] static IMAGE_DEF: ImageDef` | Faible |
| `crispy-bootloader/src/peripherals.rs` | API `rp235x-hal` (clocks, `Timer0`, GPIO, `usb::UsbBus`) | Moyenne |
| `crispy-bootloader/src/flash.rs` | **Réécriture du lookup ROM** : utiliser `rp235x_hal::rom_data` (connect/exit_xip/range_erase/range_program/flush/enter_cmd_xip). Le lookup maison `0x14/0x18` ne s'applique pas | **Élevée** |
| `crispy-bootloader/src/boot.rs` | NVIC : effacer **toutes** les lignes M33 (boucle sur `icer/icpr`), pas un seul mot ; valider les plages RAM élargies ; handoff Armv8-M (VTOR OK) | Moyenne/Élevée |
| `crispy-common-rs/src/flash.rs` | Mêmes appels ROM via `rp235x_hal::rom_data` ; tailles de banque | Moyenne |
| `crispy-common-rs/src/protocol.rs` | Constantes mémoire (adresses banques, `RAM_UPDATE_FLAG_ADDR`, tailles) à recalculer | Faible |
| `crispy-fw-sample-rs/*` | Port HAL identique au bootloader + IMAGE_DEF | Moyenne |
| `crispy-sdk-cpp/*`, `crispy-fw-sample-cpp/*` | Pico SDK 2.x (RP2350), `pico_sdk_import`, `memmap_crispy.ld`, board `pico2` | Moyenne/Élevée |
| `crispy-upload-rs/commands.rs` (`bin2uf2`) | family-id RP2350 par défaut/option | Faible |
| `tests/integration/*`, docs (`memory-map.md`, etc.) | Cartes mémoire, procédures | Faible/Moyenne |

### 2.3 Points durs (là où passe le temps réel)

1. **Bloc IMAGE_DEF + linker.** Sur RP2350 le bootrom ne démarre une image que
   si elle contient un *block loop* valide (`.start_block`). Sans lui, rien ne
   boote. C'est le changement conceptuel majeur par rapport au `boot2`.
2. **Réécriture des accès flash ROM** (`flash.rs`) : ABI et table ROM
   différentes ; à faire via `rp235x-hal::rom_data` et à valider que tout le
   chemin erase/program tourne bien depuis la RAM (XIP désactivé).
3. **Handoff Armv8-M** : nettoyage NVIC sur plusieurs registres, et vérifier le
   comportement TrustZone (le bootrom démarre en **Secure**). Pour un premier
   portage on reste en *Secure, TrustZone non utilisée*, mais c'est à tester.
4. **Refonte de la carte mémoire** (520 KB de RAM) : on peut agrandir le buffer
   d'upload (>128 KB) et la zone copiée — gain fonctionnel, mais chaque adresse
   est à recalculer et tester.
5. **Bring-up matériel** : l'essentiel du coût n'est pas le code mais le
   débogage sur cible (probe-rs/SWD, enumération USB, saut firmware).

### 2.4 Estimation portage RP2350

| Lot | Charge (j·dev) |
|---|---|
| Dépendances, cibles, config, Makefile | 0,5–1 |
| Bloc IMAGE_DEF + refonte linker (boot + fw) | 1,5–3 |
| `flash.rs` (ROM) bootloader + common | 1,5–2,5 |
| `boot.rs` handoff/NVIC/validation | 0,5–1 |
| `peripherals.rs` + `fw-sample-rs` (HAL) | 1–1,5 |
| SDK + sample C++ (Pico SDK 2.x) | 1–2 |
| Outils hôte (family-id UF2) | 0,5 |
| **Bring-up & tests d'intégration HW** | 2–4 |
| **Total RP2350** | **~9–16 j·dev (2–3 semaines)** |

> Si la cible RISC-V (Hazard3) est aussi visée, ajouter ~3–5 j (2e toolchain
> `riscv32imac`, 2e variante d'IMAGE_DEF, family-id). **Recommandation : se
> limiter d'abord à l'ARM-S (Cortex-M33).**

---

## 3. Signature du firmware

### 3.1 État actuel

Intégrité = **CRC32 seulement** (`crispy-common-rs`, `boot.rs`, `update.rs`,
host `commands.rs`). Cela ne donne **aucune authenticité** : n'importe qui
peut produire un binaire avec le bon CRC. Objectif : le bootloader ne doit
**accepter et/ou démarrer** que des firmwares signés par une clé privée de
confiance.

### 3.2 Deux approches (complémentaires)

**Option A — Signature logicielle dans le bootloader (indépendante de la puce, recommandée comme socle).**

- Algo conseillé : **Ed25519** (signature 64 o, clé publique 32 o, hash
  SHA-512 interne). Crates `no_std` : `ed25519-dalek` (no_std), ou
  **`salty`** (Ed25519 optimisé Cortex-M, idéal RP2040 M0+), ou
  `ed25519-compact`. Alternative ECDSA P-256 (`p256`/RustCrypto) plus lourde
  sur M0+, confortable sur M33.
- **Clé publique** embarquée dans le binaire du bootloader ; **clé privée**
  conservée côté hôte/CI (jamais sur la cible).
- L'hôte calcule la signature de l'image firmware ; elle est transmise via le
  protocole et stockée (en `BootData` ou en en-tête du firmware).
- Le bootloader **vérifie la signature** :
  - à l'**upload** (à `FinishUpdate`, après le CRC) — obligatoire ;
  - au **boot** (recommandé pour une vraie racine de confiance : empêche
    qu'un firmware écrit par un autre chemin — SWD, etc. — soit exécuté).
    Coût : un hash de ~192 KB par boot (accéléré par le **SHA-256 matériel**
    du RP2350 si on choisit un schéma à base de SHA-256, ex. Ed25519ph ou
    ECDSA-P256).
- Indépendant de la puce ⇒ marche **sur RP2040 et RP2350**.

**Option B — Secure boot matériel du RP2350 (RP2350 uniquement, en complément).**

- Le bootrom RP2350 sait vérifier un **IMAGE_DEF signé** (ECDSA **secp256k1**)
  contre un hash de clé publique gravé en **OTP**. C'est une racine de
  confiance matérielle.
- ⚠️ Cela sécurise **le bootloader lui-même** (la première image que le bootrom
  charge), **pas** automatiquement les images A/B que notre bootloader copie en
  RAM. Donc B ne remplace pas A : il faut **A pour les banques firmware**, et
  B est un *plus* pour verrouiller le bootloader.
- ⚠️ La gravure OTP est **irréversible** et risquée (un mauvais paramétrage
  brique la carte). À réserver à une phase ultérieure / production.

### 3.3 Recommandation

1. **Socle = Option A, Ed25519**, vérification à l'upload **et** au boot,
   indépendante de la puce (livrable utile même avant le portage RP2350).
2. Sur RP2350, choisir un schéma exploitant le **SHA-256 matériel** si la
   vérification au boot devient coûteuse (sinon Ed25519 pur convient).
3. **Option B (secure boot OTP) en phase 2**, une fois le bootloader stabilisé
   sur RP2350, pour une chaîne de confiance complète.

### 3.4 Impact fichier par fichier (Option A)

| Fichier | Modif. | Difficulté |
|---|---|---|
| `crispy-common-rs/src/protocol.rs` | **`BootData` v2** : passer de 32 o à une structure versionnée incluant `sig` (64 o) + `hash`/longueur ; champ `version` de schéma. Le `const assert == 32` saute (le secteur de 4 KB laisse la place). Étendre `StartUpdate` ou ajouter `FinishUpdateSigned { signature }` | **Élevée** (compat ascendante) |
| `crispy-bootloader/src/update.rs` | Vérifier la signature à `FinishUpdate` (sur le buffer RAM) avant commit ; stocker la signature | Moyenne |
| `crispy-bootloader/src/boot.rs` | `validate_bank_*` : ajouter la **vérif. signature au boot** (hash flash + verify) ; rejeter si invalide | Moyenne/Élevée |
| `crispy-bootloader` (nouveau module `crypto.rs` + clé publique) | Intégrer la crate de vérif. + clé publique embarquée | Moyenne |
| `crispy-bootloader/Cargo.toml` / `common` | Ajouter `salty`/`ed25519-dalek`, `sha2`/`sha-512` no_std | Faible |
| `crispy-upload-rs` (+ build) | Étape de **signature** côté hôte (charger clé privée, signer l'image) ; sous-commande `sign` / option `--key` ; envoi de la signature | Moyenne |
| **Outillage de clés** (nouveau) | `keygen` (génère paire de clés), gestion sûre de la clé privée (fichier/CI/HSM) | Moyenne |
| `crispy-upload-python` / `crispy-common-python` | Parité protocole (au moins lecture/format), idéalement signature | Moyenne |
| `crispy-sdk-cpp` / `boot_data.*` | Parité `BootData` v2 (le firmware lit ces champs) | Moyenne |
| Tests | **Tests négatifs** indispensables : firmware altéré / mauvaise clé ⇒ rejet, au boot et à l'upload | Moyenne/Élevée |
| Docs (`protocol.md`, `boot-data.md`, `memory-map.md`, how-to signer) | Mise à jour | Moyenne |

### 3.5 Estimation signature (Option A)

| Lot | Charge (j·dev) |
|---|---|
| Choix algo + outillage clés (keygen, signature hôte) | 1,5–2,5 |
| Extension protocole + `BootData` v2 + compat | 1,5–2 |
| Vérif. bootloader (upload + boot) + module crypto | 2–3 |
| Parité hôte (upload-rs) + Python | 1–2 |
| Parité SDK C++ (lecture champs) | 0,5–1 |
| Tests (unitaires + intégration + cas négatifs) | 2–3 |
| Docs | 1 |
| **Total signature** | **~9,5–14,5 j·dev (2–3 semaines)** |

> Option B (secure boot OTP RP2350) : **+3–6 j** (étude OTP, scripts picotool de
> signature de l'IMAGE_DEF, procédure de provisioning, tests irréversibles sur
> cartes sacrifiées). À planifier séparément vu le risque.

---

## 4. Charge totale et séquencement conseillé

| Phase | Contenu | Charge |
|---|---|---|
| 0 | Cadrage : algo de signature, format `BootData` v2, gestion de la clé privée (cf. §5) | 0,5–1 j |
| 1 | **Signature Option A sur la base RP2040 existante** (livrable testable tôt) | ~10–14 j |
| 2 | **Portage RP2350** (ARM-S) | ~9–16 j |
| 3 | Intégration signature ⇄ RP2350 (SHA-256 HW, vérif. au boot, perfs) | ~2–4 j |
| 4 (option) | Secure boot OTP RP2350 (option B) | ~3–6 j |

**Total (phases 1–3, un dev embarqué Rust expérimenté, hardware dispo) :
~4 à 6 semaines.** Le facteur de risque dominant est le **bring-up matériel**
RP2350 (linker/IMAGE_DEF/ROM flash/handoff) et les **tests sur cible**, pas le
volume de code.

Faire la signature **avant** le portage permet de la valider sur du matériel
maîtrisé (RP2040), puis de ne traiter qu'un problème à la fois pendant le
portage.

---

## 5. Décisions à trancher avant de démarrer

1. **Cible(s) RP2350** : ARM (Cortex-M33) seul, ou aussi RISC-V (Hazard3) ?
   (recommandé : ARM-S d'abord).
2. **Algo de signature** : Ed25519 (recommandé) vs ECDSA P-256/secp256k1
   (utile si on veut s'aligner sur le secure boot bootrom en option B).
3. **Quand vérifier** : upload seulement, ou upload **+ boot** (recommandé pour
   une vraie sécurité).
4. **Où stocker la signature** : `BootData` v2 vs en-tête appended au firmware.
5. **Gestion de la clé privée** : fichier local, secret CI, ou HSM/KMS ?
6. **Compatibilité ascendante** : doit-on encore accepter des firmwares non
   signés (mode transition) ou exiger la signature dès le départ ?
7. **Secure boot OTP (option B)** : dans le périmètre ou phase ultérieure ?
   (irréversible — à isoler).

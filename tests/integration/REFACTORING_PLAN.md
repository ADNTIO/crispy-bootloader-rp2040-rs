# Plan de refactoring : Lib d'instrumentation `crispy_board`

## Objectif

Extraire le code d'instrumentation hardware de `boot/hardware.py` (311 lignes) dans un package Python propre `crispy_board/`, réutilisable par tous les tests d'intégration. Éliminer les duplications de code identifiées.

---

## Structure cible

```
tests/integration/
    crispy_board/                 # NOUVEAU package
    ├── __init__.py               # Ré-exports pour import facile
    ├── constants.py              # Constantes partagées (adresses, PIDs, chemins)
    ├── probe.py                  # Wrapper subprocess probe-rs
    ├── flash.py                  # Opérations SWD + UF2
    ├── discovery.py              # Découverte ports USB / montage RPI-RP2
    ├── serial.py                 # Utilitaires port série
    └── cargo.py                  # Helpers cargo build / crispy-upload
    boot/
    ├── hardware.py               # SUPPRIMÉ (shim temporaire puis suppression)
    ├── conftest.py               # SIMPLIFIÉ
    ├── bootsequence/
    ├── deployment/
    └── version/
    conftest.py                   # SIMPLIFIÉ (suppression hack sys.path)
    pyproject.toml                # MODIFIÉ (ajout pythonpath)
```

---

## Duplications à éliminer

| Pattern | Occurrences actuelles | Après refactoring |
|---------|----------------------|-------------------|
| Tempfile + probe-rs download + cleanup | 3 (`hardware.py` x2, `test_deployment.py` x1) | 1 (`probe.download_binary`) |
| Boucle polling avec timeout | 3 (`find_rpi_rp2_mount`, `find_firmware_port`, `wait_for_serial_banner`) | 1 (`discovery.poll_until`) |
| `_project_root()` via parent traversal | 3 (`conftest.py`, `test_deployment.py`, `test_version.py`) | 1 (`cargo.project_root_from`) |
| Cargo build subprocess boilerplate | 3 (`bootsequence/conftest`, `test_version` x2) | 1 (`cargo.build_artifacts`) |
| Gestion erreur probe-rs (`if not success: print`) | 6 (`hardware.py`) | Centralisé dans `probe.run()` |

---

## Modules détaillés

### `constants.py`

Sources : `hardware.py:15-18`, `test_deployment.py:38-46`, `test_version.py:24`

```python
# Chip
CHIP = "rp2040"

# Adresses mémoire
RAM_UPDATE_FLAG_ADDR = 0x2003_BFF0
RAM_UPDATE_MAGIC     = 0x0FDA_7E00
BOOT_DATA_ADDR       = 0x1019_0000
BOOT2_ADDR           = 0x1000_0000
BOOT_DATA_SECTOR_SIZE = 4096
BOOT2_SIZE           = 256

# USB IDs
DEFAULT_VID      = "2e8a"
PID_BOOTLOADER   = "000a"
PID_FW_RUST      = "000b"

# Build
EMBEDDED_TARGET = "thumbv6m-none-eabi"
```

### `probe.py`

Source : `hardware.py:21-25` + pattern tempfile dupliqué

```python
@dataclass
class ProbeResult:
    success: bool
    output: str

def run(*args, timeout: float = 30.0) -> ProbeResult:
    """Exécute une commande probe-rs."""

def download_binary(data: bytes, base_address: int, timeout: float = 30.0) -> ProbeResult:
    """Écrit data en flash via tempfile + probe-rs download.
    Factorise le pattern dupliqué 3x (erase_boot_data, force_bootsel, test_deployment)."""
```

### `flash.py`

Source : `hardware.py:28-141, 203-231`

```python
def flash_elf(elf_path: Path) -> bool
    # hardware.py:28-34

def erase_flash() -> bool
    # hardware.py:37-43

def reset_device() -> bool
    # hardware.py:46-49

def erase_boot_data() -> bool
    # hardware.py:52-72 → réécrit avec probe.download_binary()

def enter_update_mode_via_swd() -> bool
    # hardware.py:75-104

def force_bootsel_mode() -> bool
    # hardware.py:107-141 → réécrit avec probe.download_binary()

def flash_uf2(uf2_path: Path, timeout: float = 15.0) -> bool
    # hardware.py:203-231
```

### `discovery.py`

Source : `hardware.py:144-267`

```python
T = TypeVar("T")

def poll_until(predicate: Callable[[], T | None], timeout: float,
               interval: float = 0.5, description: str = "") -> T:
    """Boucle de polling générique. Remplace les 3 while-loops identiques."""

def find_rpi_rp2_mount(timeout: float = 15.0) -> Path
    # hardware.py:144-191 → refactorisé avec poll_until

def find_firmware_port(pid: str, timeout: float = 10.0, vid: str = DEFAULT_VID) -> str
    # hardware.py:239-267 → refactorisé avec poll_until

def find_bootloader_port(timeout: float = 10.0) -> str
    # hardware.py:234-236
```

### `serial.py`

Source : `hardware.py:270-291`

```python
def wait_for_serial_banner(port: str, expected_text: str, timeout: float = 10.0) -> str
    # hardware.py:270-291
```

### `cargo.py`

Source : `hardware.py:294-311`, patterns dupliqués dans les tests

```python
def project_root_from(reference_file: str) -> Path:
    """Trouve la racine du projet en remontant jusqu'à Cargo.toml.
    Remplace les 3 implémentations par comptage de parents."""

def run_crispy_upload(project_root: Path, port: str, *args: str) -> tuple[bool, str, str]
    # hardware.py:294-311

def build_artifacts(root: Path, targets: list[str], timeout: float = 120) -> subprocess.CompletedProcess:
    """Helper make/cargo build. Factorise le boilerplate dupliqué dans les tests."""
```

### `__init__.py`

```python
from crispy_board.constants import *
from crispy_board.probe import run as run_probe_rs, download_binary
from crispy_board.flash import (
    flash_elf, erase_flash, reset_device, erase_boot_data,
    enter_update_mode_via_swd, force_bootsel_mode, flash_uf2,
)
from crispy_board.discovery import find_rpi_rp2_mount, find_firmware_port, find_bootloader_port
from crispy_board.serial import wait_for_serial_banner
from crispy_board.cargo import run_crispy_upload, build_artifacts, project_root_from
```

---

## Étapes de migration

### Étape 1 : Créer le package `crispy_board/`

Créer les 7 fichiers du package. Implémenter dans l'ordre :
1. `constants.py` (pas de dépendances)
2. `probe.py` (dépend de constants)
3. `discovery.py` (dépend de constants, introduit `poll_until`)
4. `flash.py` (dépend de probe + discovery)
5. `serial.py` (standalone)
6. `cargo.py` (standalone)
7. `__init__.py` (ré-exports)

### Étape 2 : Configurer les imports

Modifier `pyproject.toml` :
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

### Étape 3 : Shim temporaire `hardware.py`

Remplacer le contenu de `hardware.py` par :
```python
"""Backward-compatible re-exports. Importer depuis crispy_board à la place."""
from crispy_board import *  # noqa: F401,F403
```

Ceci garantit **zéro cassure** : tous les `from hardware import X` continuent de fonctionner.

### Étape 4 : Supprimer le hack `sys.path`

Dans `tests/integration/conftest.py`, supprimer les lignes 16-19 qui ajoutent `boot/` au `sys.path`.

### Étape 5 : Migrer les imports dans les tests

Fichier par fichier, remplacer `from hardware import ...` par `from crispy_board import ...` :
- `boot/bootsequence/conftest.py:11-16`
- `boot/deployment/test_deployment.py:28-35`

### Étape 6 : Éliminer le code dupliqué dans les tests

- `test_deployment.py:91-121` → remplacer le bloc inline par `crispy_board.erase_boot_data()`
- `test_deployment.py:68-69` → remplacer par `crispy_board.project_root_from(__file__)`
- `test_version.py:34-35` → idem
- `test_version.py:46-63` → remplacer par `crispy_board.build_artifacts(...)`

### Étape 7 : Supprimer `hardware.py`

Une fois tous les imports migrés, supprimer le shim.

---

## Risques et mitigations

| Risque | Mitigation |
|--------|-----------|
| Casser les tests existants | Le shim `hardware.py` assure la rétrocompatibilité pendant la migration |
| Nouvelles dépendances | Aucune : tout est stdlib + pyserial (déjà en dépendance) |
| `poll_until` types de retour variés | Générique avec `TypeVar` : retourne `T | None`, lève `TimeoutError` |
| `project_root_from` fragile | Remonte les parents jusqu'à trouver `Cargo.toml` au lieu de compter |

#!/usr/bin/env bash
set -euo pipefail

tag="${1:-${GITHUB_REF_NAME:-}}"
if [[ -z "${tag}" && -n "${GITHUB_REF:-}" ]]; then
  tag="${GITHUB_REF##*/}"
fi

if [[ -z "${tag}" ]]; then
  echo "error: no tag provided (expected vX.Y.Z as arg or via GITHUB_REF_NAME)." >&2
  exit 1
fi

if [[ ! "${tag}" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
  echo "error: invalid tag '${tag}', expected vX.Y.Z." >&2
  exit 1
fi

version="${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.${BASH_REMATCH[3]}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

mapfile -t cargo_manifests < <(
  cd "${repo_root}"
  git ls-files -- "Cargo.toml" "*/Cargo.toml"
)

if [[ "${#cargo_manifests[@]}" -eq 0 ]]; then
  echo "error: no Cargo.toml files found." >&2
  exit 1
fi

for manifest in "${cargo_manifests[@]}"; do
  manifest_path="${repo_root}/${manifest}"

  # Keep package versions aligned with the release tag.
  sed -E -i 's/^version = "[0-9]+\.[0-9]+\.[0-9]+"/version = "'"${version}"'"/' "${manifest_path}"

  # Update local crispy-* dependency versions when pinned in inline tables.
  sed -E -i \
    's/^(crispy-(bootloader|common|fw-sample-rs|upload)[[:space:]]*=[[:space:]]*\{[^}]*version[[:space:]]*=[[:space:]]*")[0-9]+\.[0-9]+\.[0-9]+(".*\})/\1'"${version}"'\3/' \
    "${manifest_path}"
done

echo "Synchronized Cargo manifests to ${version} from tag ${tag}."

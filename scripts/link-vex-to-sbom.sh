#!/usr/bin/env bash
# Réécrit les affects[].ref d'un VEX (PURL) en BOM-Link vers le SBOM courant :
#   pkg:cargo/x@1.2.3  ->  urn:cdx:<serialNumber>/<version>#<bom-ref>
# Échoue si un PURL n'existe pas dans le SBOM.
# Usage : link-vex-to-sbom.sh <sbom.cdx.json> <vex.cdx.json> <sortie.cdx.json>
set -euo pipefail

[[ $# -eq 3 ]] || { echo "Usage: $0 <sbom> <vex> <output>" >&2; exit 2; }
sbom=$1 vex=$2 out=$3

jq --slurpfile bom "$sbom" '
  $bom[0] as $b
  | ($b.serialNumber // error("SBOM without serialNumber") | sub("^urn:uuid:"; "")) as $uuid
  | ($b.version // 1) as $ver
  | ([$b | .. | objects | select(.purl? and .["bom-ref"]?) | {key: .purl, value: .["bom-ref"]}]
     | from_entries) as $refs
  | .vulnerabilities[].affects[].ref |= (
      if startswith("pkg:") then
        "urn:cdx:\($uuid)/\($ver)#\($refs[.] // error("PURL not found in SBOM: \(.)"))"
      else . end)
' "$vex" > "$out"

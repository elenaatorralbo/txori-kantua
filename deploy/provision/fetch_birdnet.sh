#!/usr/bin/env bash
# Downloads and verifies the BirdNET V2.4 TFLite models (issue #8).
#
#   sudo deploy/provision/fetch_birdnet.sh                  # into /opt/txori-kantua/models
#   deploy/provision/fetch_birdnet.sh --dest ~/birdnet      # anywhere, without sudo
#   deploy/provision/fetch_birdnet.sh --only int8           # a single precision
#
# Source: BirdNET Model V2.4, https://doi.org/10.5281/zenodo.15050749
# Licence: CC BY-NC 4.0 (non-commercial use, attribution required). The models
# are not stored in Git. The SHA-256 values below were computed on 17/11/2026
# from archives whose MD5 matched the checksums published by Zenodo.
#
# Result: <dest>/birdnet-v2.4/{fp32,fp16,int8}/audio-model*.tflite + labels/
set -euo pipefail

DEST="${TXORI_HOME:-/opt/txori-kantua}/models"
ONLY=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dest) DEST="${2:?missing value}"; shift 2 ;;
    --only) ONLY="${2:?missing value}"; shift 2 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

BASE="https://zenodo.org/records/15050749/files"
declare -A ARCHIVE=(
  [fp32]="BirdNET_v2.4_tflite.zip"
  [fp16]="BirdNET_v2.4_tflite_fp16.zip"
  [int8]="BirdNET_v2.4_tflite_int8.zip"
)
declare -A SHA256=(
  [fp32]="31377e128d86fe7b65fa91b206b8804bad1cd934e624bbe6e7c1788170c95e57"
  [fp16]="55369cc3804b3b23b877375f2b7d6bea2dbe95879a1c9d31cb79d377dcb4e6da"
  [int8]="48664fe911164d42ab8a5da77f285f69de5077fd15b580de59bf8220688a154f"
)

command -v curl >/dev/null || { echo "curl is required" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }

TARGET="$DEST/birdnet-v2.4"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$TARGET"

for precision in fp32 fp16 int8; do
  [ -n "$ONLY" ] && [ "$ONLY" != "$precision" ] && continue
  zip="$WORK/${ARCHIVE[$precision]}"
  echo "[birdnet] downloading $precision (${ARCHIVE[$precision]})"
  curl -fsSL --retry 3 --retry-delay 10 -o "$zip" "$BASE/${ARCHIVE[$precision]}"
  echo "${SHA256[$precision]}  $zip" | sha256sum --check --quiet \
    || { echo "[birdnet] checksum mismatch for $precision: not installed" >&2; exit 1; }
  rm -rf "${TARGET:?}/$precision"
  mkdir -p "$TARGET/$precision"
  # The archive also holds meta-model.tflite (location/season filter, issue #17).
  python3 -m zipfile -e "$zip" "$TARGET/$precision/"
done

cat > "$TARGET/SOURCE.txt" <<EOF
BirdNET Model V2.4 (Kahl et al., K. Lisa Yang Center for Conservation
Bioacoustics, Cornell Lab of Ornithology; Chemnitz University of Technology).
https://doi.org/10.5281/zenodo.15050749  Licence: CC BY-NC 4.0
Downloaded: $(date -u +%Y-%m-%dT%H:%M:%SZ) by deploy/provision/fetch_birdnet.sh
EOF
echo "[birdnet] installed in $TARGET"
find "$TARGET" -name '*.tflite' -exec ls -l {} \;

#!/usr/bin/env bash
# Measure the SHA256 of a Garage release's binaries (every architecture the node role
# supports) and add them to roles/node/vars/main.yml: the collection's trust root
# (docs/design.md, principle 2). The collection ships no default version, so nothing else
# changes.
#
# Usage: scripts/update-checksums.sh [vX.Y.Z[-pre]]   (no argument: the latest stable release)
#
# Writes the version handled to $GITHUB_OUTPUT when set. Exits 0 without changes when the
# version is already there.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
vars_file="${VARS_FILE:-$repo_root/roles/node/vars/main.yml}"

releases_api="https://git.deuxfleurs.fr/api/v1/repos/Deuxfleurs/garage/releases"
download_base="https://garagehq.deuxfleurs.fr/_releases"
# The order of the existing entries in vars/main.yml.
arches=(
  x86_64-unknown-linux-musl
  aarch64-unknown-linux-musl
  armv6l-unknown-linux-musleabihf
  i686-unknown-linux-musl
)

version="${1:-}"
if [[ -z "$version" ]]; then
  # Garage maintains parallel release lines (v1.x next to v2.x): the newest by date isn't
  # the latest. Take the highest stable version.
  version=$(curl -fsSL "$releases_api?limit=30" \
    | python3 -c 'import json, sys; print("\n".join(r["tag_name"] for r in json.load(sys.stdin) if not r["prerelease"] and not r["draft"]))' \
    | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)
fi

if [[ ! "$version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$ ]]; then
  echo "ERROR: '$version' is not a Garage version (vX.Y.Z or vX.Y.Z-pre)" >&2
  exit 1
fi
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "version=$version" >> "$GITHUB_OUTPUT"
fi

if grep -q "^  ${version}:\$" "$vars_file"; then
  echo "The checksums of $version are already in $vars_file."
  exit 0
fi

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT

declare -A sums
for arch in "${arches[@]}"; do
  url="$download_base/$version/$arch/garage"
  echo "Downloading $url"
  curl -fsSL --retry 3 --max-time 900 -o "$tmpdir/garage" "$url"
  sums[$arch]=$(sha256sum "$tmpdir/garage" | cut -d' ' -f1)
  echo "  $arch: ${sums[$arch]}"
done

{
  echo "  ${version}:"
  for arch in "${arches[@]}"; do
    echo "    ${arch}: \"${sums[$arch]}\""
  done
} >> "$vars_file"
echo "Added the checksums of $version to $vars_file."

#!/bin/sh
# Install the speaker CLI

set -eu

REPO="${REPO:-migsterrrrr/speaker}"
REF="${REF:-master}"
ROOT_URL="${ROOT_URL:-https://raw.githubusercontent.com/$REPO/$REF}"
BASE_URL="${BASE_URL:-$ROOT_URL/cli}"
SKILL_URL="${SKILL_URL:-$ROOT_URL/SKILL.md}"
CONFIG_DIR="${CONFIG_DIR:-$HOME/.speaker}"
SCHEMA_DIR="$CONFIG_DIR/tables"

fail() {
  echo "Error: $1" >&2
  exit 1
}

cleanup() {
  [ -n "${TMP_SPEAKER:-}" ] && rm -f "$TMP_SPEAKER"
  [ -n "${TMP_DOCS:-}" ] && rm -f "$TMP_DOCS"
  [ -n "${TMP_SCHEMA_DIR:-}" ] && rm -rf "$TMP_SCHEMA_DIR"
}

download() {
  url="$1"
  out="$2"

  if ! curl --fail --show-error --silent --location \
    --retry 3 --retry-delay 1 --connect-timeout 10 --max-time 60 \
    "$url" -o "$out"; then
    fail "Failed to download: $url"
  fi

  [ -s "$out" ] || fail "Downloaded file is empty: $url"
}

is_writable_dir_or_parent() {
  dir="$1"
  if [ -d "$dir" ]; then
    [ -w "$dir" ]
    return
  fi
  parent=$(dirname "$dir")
  [ -d "$parent" ] && [ -w "$parent" ]
}

choose_bindir() {
  if [ -n "${BINDIR:-}" ]; then
    printf '%s\n' "$BINDIR"
    return
  fi
  if [ -n "${INSTALL_DIR:-}" ]; then
    printf '%s\n' "$INSTALL_DIR"
    return
  fi
  if [ -n "${PREFIX:-}" ]; then
    printf '%s\n' "$PREFIX/bin"
    return
  fi
  if is_writable_dir_or_parent "/usr/local/bin"; then
    printf '%s\n' "/usr/local/bin"
    return
  fi
  printf '%s\n' "$HOME/.local/bin"
}

path_has_dir() {
  case ":${PATH:-}:" in
    *":$1:"*) return 0 ;;
    *) return 1 ;;
  esac
}

schema_artifacts() {
  cat <<'EOF'
_mesh.yaml|mesh.yaml
people.nucleus.yaml|tables/people/nucleus.yaml
people.contacts.yaml|tables/people/contacts.yaml
people.roles_history.yaml|tables/people/roles_history.yaml
people.education.yaml|tables/people/education.yaml
people.repos.yaml|tables/people/repos.yaml
companies.nucleus.yaml|tables/companies/nucleus.yaml
companies.identifiers.yaml|tables/companies/identifiers.yaml
companies.metrics.yaml|tables/companies/metrics.yaml
companies.industry_keywords.yaml|tables/companies/industry_keywords.yaml
companies.jobs.yaml|tables/companies/jobs.yaml
companies.posts.yaml|tables/companies/posts.yaml
companies.competitors.yaml|tables/companies/competitors.yaml
companies.funding_rounds.yaml|tables/companies/funding_rounds.yaml
companies.web_outlinks.yaml|tables/companies/web_outlinks.yaml
web.domain_entity_bridge.yaml|tables/web/domain_entity_bridge.yaml
web.pages.yaml|tables/web/pages.yaml
EOF
}

command -v curl >/dev/null 2>&1 || fail "curl is required"
command -v mktemp >/dev/null 2>&1 || fail "mktemp is required"

BINDIR="$(choose_bindir)"
TARGET="$BINDIR/speaker"

mkdir -p "$BINDIR" || fail "Could not create bin directory: $BINDIR"
[ -w "$BINDIR" ] || fail "No write access to $BINDIR. Set BINDIR=/your/bin or PREFIX=/your/prefix"

TMP_SPEAKER="$(mktemp)"
TMP_DOCS="$(mktemp)"
TMP_SCHEMA_DIR="$(mktemp -d)"
trap cleanup EXIT INT TERM HUP

echo "Installing speaker CLI from $REPO@$REF..."

download "$BASE_URL/speaker" "$TMP_SPEAKER"
download "$SKILL_URL" "$TMP_DOCS"

schema_artifacts | while IFS='|' read -r dst src; do
  [ -n "$dst" ] || continue
  download "$ROOT_URL/$src" "$TMP_SCHEMA_DIR/$dst"
done

mkdir -p "$CONFIG_DIR"
mkdir -p "$SCHEMA_DIR"
rm -f "$SCHEMA_DIR"/*.yaml

cp "$TMP_SPEAKER" "$TARGET"
chmod 755 "$TARGET"

cp "$TMP_DOCS" "$CONFIG_DIR/SKILL.md"
chmod 644 "$CONFIG_DIR/SKILL.md"

cp "$TMP_SCHEMA_DIR"/*.yaml "$SCHEMA_DIR/"
chmod 644 "$SCHEMA_DIR"/*.yaml

echo ""
echo "  ✓ speaker installed to $TARGET"
echo "  ✓ Agent docs saved to $CONFIG_DIR/SKILL.md"
echo "  ✓ Schema docs saved to $SCHEMA_DIR"
if ! path_has_dir "$BINDIR"; then
  echo ""
  echo "  Add this to your shell profile so 'speaker' is on PATH:"
  echo "    export PATH=\"$BINDIR:\$PATH\""
fi
echo ""
echo "  Get started:"
echo "    speaker signup          Create an account"
echo "    speaker help            See all commands"
echo ""
echo "  Overrides:"
echo "    PREFIX=/path            Install to PREFIX/bin (npm-style)"
echo "    BINDIR=/path            Install to an exact bin directory"
echo "    REF=<tag-or-commit>     Install a specific version"
echo ""

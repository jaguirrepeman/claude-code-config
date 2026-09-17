#!/usr/bin/env sh
# Instala (o comprueba) esta configuración en ~/.claude. Funciona en Git Bash y en Linux; en la
# máquina corporativa Group Policy bloquea los .ps1, por eso esto es sh y no PowerShell.
#
#   sh install.sh [--machine personal|deloitte]   copia CLAUDE.md, machine.md, skills, agents y hooks
#   sh install.sh --check [--machine ...]         no copia: dice qué difiere entre el repo y ~/.claude
#
# No toca ~/.claude/settings.json: los bloques "hooks" y "permissions" se fusionan a mano desde
# settings/*.snippet.json (ver README). Una copia ciega pisaría los permisos aceptados en caliente.
set -eu

MODE=install
MACHINE=personal
while [ $# -gt 0 ]; do
  case "$1" in
    --check) MODE=check ;;
    --machine) shift; MACHINE="$1" ;;
    *) echo "uso: sh install.sh [--check] [--machine personal|deloitte]" >&2; exit 2 ;;
  esac
  shift
done

HERE=$(cd "$(dirname "$0")" && pwd)
DEST="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
[ -f "$HERE/machines/$MACHINE.md" ] || { echo "no existe machines/$MACHINE.md" >&2; exit 2; }

# Pares origen:destino, relativos a HERE y a DEST.
pairs() {
  echo "CLAUDE.md:CLAUDE.md"
  echo "machines/$MACHINE.md:machine.md"
  for f in "$HERE"/agents/*.md; do echo "agents/$(basename "$f"):agents/$(basename "$f")"; done
  for f in "$HERE"/hooks/*.py; do echo "hooks/$(basename "$f"):hooks/$(basename "$f")"; done
  for d in "$HERE"/skills/*/; do
    n=$(basename "$d")
    for f in "$d"*; do echo "skills/$n/$(basename "$f"):skills/$n/$(basename "$f")"; done
  done
}

report=$(pairs | while IFS=: read -r src dst; do
  if [ "$MODE" = check ]; then
    if [ ! -f "$DEST/$dst" ]; then
      echo "FALTA   $dst"
    elif ! cmp -s "$HERE/$src" "$DEST/$dst"; then
      echo "DIFIERE $dst"
    else
      echo "igual   $dst"
    fi
  else
    mkdir -p "$(dirname "$DEST/$dst")"
    cp "$HERE/$src" "$DEST/$dst"
    echo "copiado $dst"
  fi
done)
printf '%s\n' "$report"
drift=0
printf '%s\n' "$report" | grep -q -E '^(FALTA|DIFIERE)' && drift=1

if [ "$MODE" = check ]; then
  [ "$drift" -eq 0 ] && echo "Sin drift: ~/.claude coincide con el repo." || { echo "Hay drift: sh install.sh para actualizar."; exit 1; }
else
  echo "Instalado en $DEST. Falta fusionar a mano settings/*.snippet.json en $DEST/settings.json."
fi

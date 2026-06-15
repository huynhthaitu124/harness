#!/usr/bin/env bash
set -euo pipefail

HARNESS_ROOT="$(cd "$(dirname "$0")" && pwd)"
HARNESS_BIN="$HARNESS_ROOT/scripts/harness"

# On Windows (Git Bash / MINGW) — add scripts/ to PATH via PowerShell instead
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
  SCRIPTS_DIR="$(cygpath -w "$HARNESS_ROOT/scripts" 2>/dev/null || echo "$HARNESS_ROOT/scripts")"
  powershell.exe -NoProfile -Command "
    \$p = [Environment]::GetEnvironmentVariable('PATH','User');
    if (\$p -notlike '*$SCRIPTS_DIR*') {
      [Environment]::SetEnvironmentVariable('PATH', '$SCRIPTS_DIR;' + \$p, 'User');
      Write-Host 'Added to user PATH: $SCRIPTS_DIR'
    } else {
      Write-Host 'harness already on PATH'
    }
  "
  echo ""
  echo "Restart your terminal, then use: harness init"
  exit 0
fi

# Prefer /usr/local/bin if writable, else ~/.local/bin
if [ -w /usr/local/bin ]; then
  LINK=/usr/local/bin/harness
else
  mkdir -p "$HOME/.local/bin"
  LINK="$HOME/.local/bin/harness"
fi

if [ -L "$LINK" ] && [ "$(readlink "$LINK")" = "$HARNESS_BIN" ]; then
  echo "harness already installed → $LINK"
else
  ln -sf "$HARNESS_BIN" "$LINK"
  echo "installed: $LINK → $HARNESS_BIN"
fi

# Add ~/.local/bin to PATH if needed
if [[ "$LINK" == "$HOME/.local/bin/harness" ]]; then
  for RC in "$HOME/.zshrc" "$HOME/.bashrc"; do
    if [ -f "$RC" ] && grep -q '\.local/bin' "$RC"; then
      break
    fi
  done
  if ! grep -q '\.local/bin' "${HOME}/.zshrc" 2>/dev/null && ! grep -q '\.local/bin' "${HOME}/.bashrc" 2>/dev/null; then
    echo "\nexport PATH=\"$HOME/.local/bin:\$PATH\"  # added by harness install" >> "$HOME/.zshrc"
    echo "added ~/.local/bin to PATH in ~/.zshrc"
    echo "run: source ~/.zshrc"
  fi
fi

echo ""
echo "Usage (run from inside any project):"
echo "  harness init"
echo "  harness eject"
echo "  harness status"
echo "  harness grill"

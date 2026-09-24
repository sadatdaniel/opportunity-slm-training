#!/usr/bin/env bash
set -euo pipefail
PKG=/root/.local/share/uv/tools/google-colab-cli/lib/python3.12/site-packages/colab_cli
ls -la "$PKG" | head -20
echo "---inlined oauth config---"
cat "$PKG/oauth_config.json" 2>/dev/null || echo "NO INLINED CONFIG"
echo "---redirect uri + scopes---"
grep -n "REMOTE_REDIRECT_URI\|PUBLIC_SCOPES" "$PKG/auth.py" | head -5

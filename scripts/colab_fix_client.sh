#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
PY=/root/.local/share/uv/tools/google-colab-cli/bin/python
uv pip install --python "$PY" "jupyter-kernel-client @ git+https://github.com/googlecolab/jupyter-kernel-client.git" 2>&1 | tail -2
$PY -c 'import jupyter_kernel_client as j; print("JupyterSubprotocol present:", hasattr(j, "JupyterSubprotocol"))'

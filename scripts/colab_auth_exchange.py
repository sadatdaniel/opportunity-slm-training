#!/usr/bin/env python3
"""Colab CLI OAuth phase 2: exchange the authorization code and save the token.

Usage: python3 colab_auth_exchange.py <code>
Writes ~/.config/colab-cli/token.json in the exact format colab-cli reads
(Credentials.to_json via from_authorized_user_file).
"""
import json
import os
import sys
from importlib import resources

sys.path.insert(0, "/root/.local/share/uv/tools/google-colab-cli/lib/python3.12/site-packages")

from google_auth_oauthlib.flow import InstalledAppFlow
from colab_cli.auth import PUBLIC_SCOPES, REMOTE_REDIRECT_URI

code = sys.argv[1]
client_config = json.loads(resources.files("colab_cli").joinpath("oauth_config.json").read_text())
flow = InstalledAppFlow.from_client_config(client_config, PUBLIC_SCOPES)
flow.redirect_uri = REMOTE_REDIRECT_URI
with open(os.path.expanduser("~/.config/colab-cli/.code_verifier")) as fh:
    flow.code_verifier = fh.read().strip()
flow.fetch_token(code=code)

token_path = os.path.expanduser("~/.config/colab-cli/token.json")
os.makedirs(os.path.dirname(token_path), exist_ok=True)
with open(token_path, "w") as fh:
    fh.write(flow.credentials.to_json())
os.chmod(token_path, 0o600)
print(f"token saved to {token_path}")

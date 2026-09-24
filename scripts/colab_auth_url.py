#!/usr/bin/env python3
"""Colab CLI OAuth phase 1: print the authorization URL.

Mirrors colab_cli.auth's remote copy-paste flow exactly (same inlined public
client config, scopes, redirect URI) so the exchanged token is byte-compatible
with the CLI's own ~/.config/colab-cli/token.json.
"""
import json
import sys
from importlib import resources

sys.path.insert(0, "/root/.local/share/uv/tools/google-colab-cli/lib/python3.12/site-packages")

from google_auth_oauthlib.flow import InstalledAppFlow
from colab_cli.auth import PUBLIC_SCOPES, REMOTE_REDIRECT_URI

client_config = json.loads(resources.files("colab_cli").joinpath("oauth_config.json").read_text())
flow = InstalledAppFlow.from_client_config(client_config, PUBLIC_SCOPES)
flow.redirect_uri = REMOTE_REDIRECT_URI
url, _ = flow.authorization_url(prompt="consent")

# PKCE: the verifier is required at exchange time and must match this URL
import os

verifier_path = os.path.expanduser("~/.config/colab-cli/.code_verifier")
os.makedirs(os.path.dirname(verifier_path), exist_ok=True)
with open(verifier_path, "w") as fh:
    fh.write(flow.code_verifier)
os.chmod(verifier_path, 0o600)
print(url)

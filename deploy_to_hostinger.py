#!/tmp/env/bin/python
"""Set GitHub secrets + variable + trigger deploy for email-accountant"""
import base64, json, subprocess, os
from nacl import bindings

gh_token = os.environ.get('GITHUB', '')
hostinger_key = os.environ.get('HOSTINGER', '')

key_b64 = '8PEeq7vMROeiZM9fjRoA60LrSf22fxYw030K+8sKeU0='
key_id = '3380204578043523366'
key = base64.b64decode(key_b64)

repo = 'bowtiekreative/email-accountant'
api = f'https://api.github.com/repos/{repo}'
headers = ['-H', f'Authorization: token {gh_token}', '-H', 'Accept: application/vnd.github.v3+json', '-H', 'Content-Type: application/json']

def gh(method, path, data=None):
    cmd = ['curl', '-s', '-X', method] + headers + [f'{api}/{path}']
    if data:
        cmd += ['-d', json.dumps(data)]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=15)

# 1. Set HOSTINGER_VM_ID variable
print("=== Setting HOSTINGER_VM_ID variable ===")
r = gh('POST', 'actions/variables', {'name': 'HOSTINGER_VM_ID', 'value': '620544'})
if 'already exists' in r.stdout.lower():
    r = gh('PATCH', 'actions/variables/HOSTINGER_VM_ID', {'name': 'HOSTINGER_VM_ID', 'value': '620544'})
print(f"  {r.stdout[:100]}")

# 2. Set HOSTINGER_API_KEY secret
print("=== Setting HOSTINGER_API_KEY secret ===")
encrypted = bindings.crypto_box_seal(hostinger_key.encode(), key)
enc_b64 = base64.b64encode(encrypted).decode()
r = gh('PUT', f'actions/secrets/HOSTINGER_API_KEY', {'encrypted_value': enc_b64, 'key_id': key_id})
print(f"  {r.stdout[:100]}")

# 3. Trigger workflow
print("=== Triggering deploy workflow ===")
r = gh('POST', 'actions/workflows/build-images.yml/dispatches', {'ref': 'main'})
print(f"  Triggered: HTTP {r.returncode} | {r.stdout[:100]}")
print(f"  stderr: {r.stderr[:100]}")

print("\n✅ Done! Check https://github.com/bowtiekreative/email-accountant/actions for progress")
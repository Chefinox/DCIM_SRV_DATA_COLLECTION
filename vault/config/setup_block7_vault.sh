#!/usr/bin/env bash
set -e

# Configuration
VAULT_ADDR="${VAULT_ADDR:-http://10.70.0.56:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-VAULT_ROOT_TOKEN_REDACTED}"

export VAULT_ADDR
export VAULT_TOKEN

# Execute vault commands using CLI or docker exec vault
vault_cmd() {
    if command -v vault &> /dev/null; then
        vault "$@"
    else
        docker exec -e VAULT_ADDR="http://127.0.0.1:8200" -e VAULT_TOKEN="$VAULT_TOKEN" vault vault "$@"
    fi
}

echo "==> Configuring Vault for Block 7 (ST-318)..."

# 1. Write Block 7 Runtime Policy
POLICY_PATH="/home/infra/dcim_metrics_project/vault/policies/block7-runtime-policy.hcl"
if [ -f "$POLICY_PATH" ]; then
    vault_cmd policy write block7-runtime-policy - < "$POLICY_PATH"
    echo "[✓] Vault Policy 'block7-runtime-policy' created/updated successfully."
else
    echo "[!] Error: Policy file $POLICY_PATH not found."
    exit 1
fi

# 2. Write Template Key/Config at secret/dcim/jwt_verifier
vault_cmd kv put secret/dcim/jwt_verifier \
    algorithm="TEMPLATE_WAITING_FOR_IAM" \
    issuer="TEMPLATE_WAITING_FOR_IAM" \
    audience="TEMPLATE_WAITING_FOR_IAM" \
    status="PREPARED_FOR_ST318" > /dev/null

echo "[✓] Template secret path 'secret/dcim/jwt_verifier' initialized."

# 3. Output Vault Reference Handoff Information
echo "--------------------------------------------------------"
echo "Vault Handoff Information for Fadel & Fakhri:"
echo "  Vault Path Reference : secret/dcim/jwt_verifier"
echo "  Vault Auth Method     : AppRole / Token"
echo "  Runtime Policy Name   : block7-runtime-policy"
echo "--------------------------------------------------------"


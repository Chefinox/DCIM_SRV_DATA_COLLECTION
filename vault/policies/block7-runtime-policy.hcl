# Vault Least-Privilege Policy for Block 7 Analytics Runtime
# Grants read-only access to JWT verifier configuration

path "secret/data/dcim/jwt_verifier" {
  capabilities = ["read"]
}

path "secret/metadata/dcim/jwt_verifier" {
  capabilities = ["read"]
}

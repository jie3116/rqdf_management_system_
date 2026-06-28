# Reviews

Folder ini menyimpan output reviewer agent. Reviewer tidak mengubah kode kecuali diminta secara eksplisit.

## Struktur saat ini

```text
reviews/
  auth-rbac-tenant/
    auth_rbac_tenant_audit.md
    auth_rbac_tenant_remediation_backlog.md
    auth_rbac_tenant_remediation_status.md
    auth_rbac_tenant_remediation_changelog.md
  auth-tenant/
    auth_tenant_001_test_plan.md
  auth-package-003/
    auth_package_003_impact_analysis.md
    auth_package_003_phase1_review.md
    package_capability_matrix_v2.md
  auth-rate-004/
    auth_rate_004_impact_analysis.md
    auth_rate_004_verification_gate.md
    auth_rate_004_phase1_review.md
  auth-token-005/
    auth_token_005_impact_analysis.md
    auth_token_005_verification_gate.md
    auth_token_005_phase1_code_review.md
    auth_token_005_migration_deploy_gate.md
  platform-tenant/
    platform_tenant_super_admin_policy.md
    platform_tenant_inventory.md
    platform_tenant_script_review.md
  review_template.md
```

Gunakan folder per case/remediation agar artifact analysis, verification gate, code review, dan deploy gate mudah ditemukan.

## Aturan

- Cantumkan tanggal, reviewer/agent, commit atau scope file, dan dokumen spec.
- Pisahkan fakta, inferensi, dan rekomendasi.
- Setiap temuan menunjuk file/lokasi dan bukti.
- Jangan menyalin secret, token, PII, atau data production.
- Temuan HIGH/CRITICAL tidak otomatis memberi izin untuk mengubah production.
- Audit mendalam aplikasi hanya dimulai setelah approval manusia.


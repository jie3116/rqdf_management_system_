# Reviews

Folder ini menyimpan output reviewer agent. Reviewer tidak mengubah kode kecuali diminta secara eksplisit.

## Struktur yang disarankan

```text
reviews/
  <feature-or-audit-scope>/
    database_review.md
    test_report.md
    security_review.md
    performance_review.md
    code_review.md
    release_readiness.md
```

Gunakan nama scope yang stabil, misalnya `mobile-auth-refresh`, `ppdb-upload`, atau `finance-posting`.

## Aturan

- Cantumkan tanggal, reviewer/agent, commit atau scope file, dan dokumen spec.
- Pisahkan fakta, inferensi, dan rekomendasi.
- Setiap temuan menunjuk file/lokasi dan bukti.
- Jangan menyalin secret, token, PII, atau data production.
- Temuan HIGH/CRITICAL tidak otomatis memberi izin untuk mengubah production.
- Audit mendalam aplikasi hanya dimulai setelah approval manusia.


# Finance Ops Runbook

## 1) Seed Default Finance Data

Jalankan sekali per environment setelah migration:

```bash
python -m app.scripts.seed_finance_defaults
```

Di Docker:

```bash
docker compose exec web python -m app.scripts.seed_finance_defaults
```

## 2) Monthly Period Maintenance

Script maintenance:

```bash
python -m app.scripts.finance_period_maintenance
```

Fungsi default:
- Membuat periode `OPEN` untuk bulan berjalan jika belum ada.

Opsional lock periode lama:

```bash
python -m app.scripts.finance_period_maintenance --lock-old-periods
```

Target bulan spesifik:

```bash
python -m app.scripts.finance_period_maintenance --month 2026-06
```

Target tenant spesifik:

```bash
python -m app.scripts.finance_period_maintenance --tenant-id 1 --tenant-id 2
```

## 3) Suggested Cron (Server Time)

Contoh cron tanggal 1 setiap bulan pukul 00:10:

```cron
10 0 1 * * cd /opt/rq_app && docker compose exec -T web python -m app.scripts.finance_period_maintenance --lock-old-periods
```

## 4) Manual UI Safeguards

Di Admin > Finance Settings:
- Tombol `Buat/Set OPEN Periode Bulan Ini`
- Tombol `Kunci Periode Lama`

Di seluruh UI admin ada alert jika:
- Masih ada jurnal `DRAFT`
- Periode hari ini belum `OPEN`

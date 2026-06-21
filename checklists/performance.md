# Performance Review Checklist

Tandai `PASS`, `FAIL`, `N/A`, atau `NOT VERIFIED`; sertakan bukti atau asumsi volume.

## Query dan data access

- [ ] Jumlah query per request tidak tumbuh linear terhadap jumlah item.
- [ ] Relationship yang dibaca berulang menggunakan loading strategy yang tepat.
- [ ] Filter/join/order umum memiliki index yang relevan.
- [ ] Query membawa kolom dan row secukupnya.
- [ ] Count/aggregate tidak diulang tanpa alasan.
- [ ] Tenant filter diterapkan sebelum mengambil dataset besar.

## Collection dan payload

- [ ] Endpoint list memiliki pagination atau hard limit.
- [ ] Default page size dan maximum page size ditentukan.
- [ ] Response/template tidak memuat object graph berlebihan.
- [ ] Export/report besar memiliki strategi streaming/background bila diperlukan.

## CPU, memory, dan I/O

- [ ] Loop tidak melakukan query/file/network call per item.
- [ ] Parsing file, PDF, AI, push, dan external API memiliki batas dan timeout.
- [ ] Computation berulang memiliki alasan atau caching yang terukur.
- [ ] Transaction database tidak ditahan selama external I/O.

## Bukti dan prioritas

- [ ] Expected volume/cardinality dicatat.
- [ ] Cara ukur sebelum/sesudah ditentukan.
- [ ] Optimasi tidak mengubah correctness.
- [ ] Prioritas P0–P3 dan tradeoff ditulis.


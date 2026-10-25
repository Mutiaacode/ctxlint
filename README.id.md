# ctxlint

**Pemeriksa file aturan yang dibaca AI coding agent kamu.**

[English](README.md) · [Bahasa Indonesia](README.id.md)

## Penjelasan singkat

Sebelum menulis kode, agent kamu membaca file aturan: `AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, `.clinerules`, `SKILL.md`. Di situ kamu memberi tahu hal seperti "test pakai `npm test`" atau "API ada di `src/api/v2`".

Lalu kode berjalan terus. Folder diganti nama, script dihapus, satu aturan ditempel ke lima file, satu file membengkak jadi 7000 token. File aturannya tidak ikut diperbarui.

Agent tidak punya cara untuk tahu. Dia membaca aturan lama dan mengikutinya dengan patuh. Hasilnya salah, dan kamu menyalahkan modelnya.

`ctxlint` membaca file-file itu dan memberi tahu mana yang sudah tidak cocok, mana yang menunjuk sesuatu yang sudah tidak ada, mana yang isinya dobel, dan mana yang kegedean. Satu perintah, satu tabel masalah, satu skor.

```
$ ctxlint --agent hermes
skills/agent-visualization/SKILL.md:65   error  broken-ref  references `references/pixel-character-sprites.md` which does not exist
skills/office/SKILL.md:236               error  broken-ref  references `scripts/office/soffice.py` which does not exist
skills/market-analysis/SKILL.md:1        warn   cost        ~7110 tokens loaded every run (budget 4000)
skills/market-analysis/SKILL.md:129      warn   duplicate   same rule also in skills/xauusd-analysis/SKILL.md:41
skills/ui-ux-pro-max/SKILL.md:1          info   trigger     description should start with 'Use when ...'

context: 78 files, ~278950 tokens/run  ·  11 error, 31 warn  ·  score 36/100
```

Kalau ada minimal satu error, exit code-nya `1`, jadi CI bisa menolak perubahan yang bermasalah.

## Kenapa alat ini ada

Kami tidak menebak di mana masalahnya. Kami menghitungnya. Jumlah issue terbuka di tool agent populer:

| repo | `context` | `memory` | `token cost` | `observability` |
|---|---|---|---|---|
| Aider-AI/aider | 340 | 32 | 95 | 3 |
| cline/cline | 239 | 71 | 35 | 1 |
| langchain-ai/langchain | 225 | 53 | 37 | 26 |
| microsoft/autogen | 193 | 67 | 29 | 22 |

Masalah soal context dan state 10 sampai 100 kali lebih banyak daripada masalah soal memantau agent berjalan. Alat untuk memantau sudah ada dan sudah bagus. Yang belum ada: yang mengurus apa yang sebenarnya diberitahukan ke agent.

Bukti lain:

- Stack Overflow Developer Survey 2025: **66%** developer bilang frustrasi AI terbesar mereka adalah hasil yang "hampir benar, tapi tidak", dan **45%** bilang debugging kode buatan AI lebih lama.
- Studi pertanyaan soal agent di Stack Overflow (arXiv 2510.25423) menemukan observability cuma **11.6%** dari masalah agent, sementara koordinasi tool dan konfigurasi mencapai **23%**.
- Judul issue yang berulang: *"Cline auto compacts context silently"*, *"Clinerules are completely ignored"*, *"Checkpoint restore fails after internal continuations"*.

Linter tidak bisa membuat model jadi lebih pintar. Tapi dia bisa menghentikan kamu memberi informasi salah ke model — tanpa biaya tambahan.

## Instalasi

Belum ada di PyPI, jadi clone dulu:

```bash
git clone https://github.com/Mutiaacode/ctxlint
pipx install ./ctxlint          # atau: uv tool install ./ctxlint
# tidak punya pipx? jalankan langsung filenya:
python3 ctxlint/ctxlint.py --help
```

Butuh Python 3.10 ke atas. Tidak ada yang lain. Tanpa dependency, tanpa internet, tanpa API key.

## Cara pakai

```bash
ctxlint                          # periksa repo tempat kamu berada
ctxlint path/to/repo             # periksa repo lain
ctxlint --agent hermes           # periksa ~/.hermes/skills dan ~/.hermes/memories
ctxlint --quiet                  # hanya error, cocok untuk CI
ctxlint --json                   # output untuk dibaca mesin
ctxlint --ignore stale,cost      # lewati pemeriksaan yang terlalu berisik
ctxlint --max-tokens 6000        # batas token per file (default 4000)
ctxlint --max-days 90            # seberapa lama dianggap basi (default 180)
ctxlint --selftest               # jalankan tes bawaan
ctxlint --list-checks            # tampilkan semua pemeriksaan lalu keluar
```

Untuk melewati satu baris saja, taruh komentar di ujung baris itu:

```markdown
- Config ada di `config/app.yaml` <!-- ctxlint-ignore -->
```

## Yang diperiksa

| code | level | artinya |
|---|---|---|
| `broken-ref` | error | file menunjuk sesuatu yang katanya ikut dikirim (`references/x.md`, `scripts/y.py`), tapi barangnya sudah tidak ada |
| `broken-ref` | info | path yang disebut sambil lalu tidak ditemukan — mungkin cuma contoh |
| `duplicate` | warn | aturan yang sama ditulis di lebih dari satu file |
| `stale` | warn | git bilang file tidak berubah selama N hari, jadi mungkin sudah tidak cocok dengan kodenya |
| `cost` | warn | file lebih besar dari batas token, dan file ini dikirim di setiap run |
| `trigger` | info | `description` skill tidak diawali "Use when ...", jadi pemicunya tidak jelas |
| `pruned` | error | placeholder `[SKILL_PRUNED]` tertinggal di isi skill |
| `budget` | warn | file memori sudah penuh, tidak ada ruang untuk fakta baru |
| `secret` | error | ada token atau private key yang ikut ke-commit di file konteks |

Kenapa satu code punya dua level: path yang katanya ikut dikirim itu fakta yang bisa dicek, jadi statusnya error. Sedangkan `package.json` yang disebut di tengah kalimat bisa jadi cuma contoh, jadi statusnya `info`.

## Cocok untuk

Layout repo: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `CONTEXT.md`, `.cursorrules`, `.windsurfrules`, `.clinerules`, `.rules`, `.aider.conf.yml`, `.github/copilot-instructions.md`, `.github/instructions/*.md`, `.cursor/rules/*`, `.claude/**/*.md`, `skills/**/SKILL.md`.

Layout Hermes (`--agent hermes`): `~/.hermes/skills/**/SKILL.md`, `~/.hermes/memories/*.md`, `~/.hermes/AGENTS.md`, `~/.hermes/SOUL.md`.

Menambah layout lain cukup satu fungsi di `discover()`.

## CI

```yaml
name: ctxlint
on: [push, pull_request]
jobs:
  ctxlint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }   # cek basi butuh riwayat git
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: python3 ctxlint.py --quiet .
```

## Yang kamu dapat

- **Lebih sedikit run terbuang.** Referensi rusak itu instruksi salah yang langsung dipatuhi agent. Menangkapnya di linter jauh lebih murah daripada menangkapnya setelah task gagal.
- **Biaya token lebih kecil.** File konteks dikirim ulang di setiap request. Memotong 7000 token aturan basi dari task lima request itu uang nyata, setiap hari.
- **Satu repo, banyak agent.** Lima agent membaca lima file aturan berbeda. `duplicate` menunjukkan aturan mana yang sudah bercabang, jadi kamu perbaiki sumbernya, bukan gejalanya.

## Yang tidak dilakukan

- Tidak memanggil model. Tanpa jaringan, tanpa telemetri, tanpa API key. Jalan di CI dan di sandbox.
- Tidak punya dependency. Satu file, hanya standard library.
- Tidak menebak. Pemeriksaan hanya melaporkan hal yang bisa dibuktikan. Yang subjektif ditandai `info` dan tidak pernah menggagalkan build.

## Rencana

Direncanakan: `--fix` untuk menulis ulang dengan aman (pindahkan aturan dobel ke satu file), mode `ctxsync` yang menulis satu file aturan bersama untuk semua agent, pemeriksaan config MCP (server dobel, command mati), output SARIF dan deteksi konflik (dua skill memberi perintah berlawanan).

Tidak direncanakan: trace viewer lagi, platform eval, dashboard, framework.

## Kontribusi

Setiap pemeriksaan adalah satu fungsi di `ctxlint.py`: menerima `CtxFile`, mengembalikan `Finding`. Tambahkan ke `analyze()`, tambahkan fixture ke `--selftest`, lalu jalankan:

```bash
python3 ctxlint.py --selftest
```

Uji dulu setiap pemeriksaan baru ke kumpulan file nyata yang besar. Pemeriksaan yang menyala di repo sehat lebih buruk daripada tidak ada pemeriksaan.

## Lisensi

MIT. Dibuat oleh [mutiadev](https://github.com/Mutiaacode).

# ctxlint

**ESLint untuk konteks yang dibaca AI agent kamu.**

[English](README.md) · [Bahasa Indonesia](README.id.md)

Agent coding kamu membaca file aturan sebelum menyentuh satu baris kode: `AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, `.clinerules`, `SKILL.md`. File-file itu lama-lama basi. Folder diganti nama, script dihapus, aturan yang sama ditempel ke lima file, dan satu file membengkak jadi 7k token yang dikirim ulang di setiap run.

Agent tidak tahu ada yang salah. Dia membaca aturan basi itu dan mengikutinya dengan yakin.

`ctxlint` yang membaca file-file itu untuk kamu, lalu memberi tahu mana yang rusak, mati, dobel, atau terlalu mahal — sebelum agent kamu membuang satu run untuk itu.

```
$ ctxlint --agent hermes
skills/agent-visualization/SKILL.md:65   error  broken-ref  references `references/pixel-character-sprites.md` which does not exist
skills/office/SKILL.md:236               error  broken-ref  references `scripts/office/soffice.py` which does not exist
skills/market-analysis/SKILL.md:1        warn   cost        ~7110 tokens loaded every run (budget 4000)
skills/market-analysis/SKILL.md:129      warn   duplicate   same rule also in skills/xauusd-analysis/SKILL.md:41
skills/ui-ux-pro-max/SKILL.md:1          info   trigger     description should start with 'Use when ...'

context: 78 files, ~278950 tokens/run  ·  11 error, 31 warn  ·  score 36/100
```

Exit code `1` kalau ada minimal satu error, jadi bisa langsung dipasang di CI.

## Kenapa

Karena masalahnya memang di sini — ini hasil hitung, bukan perasaan. Jumlah issue terbuka di tooling agent populer:

| repo | `context` | `memory` | `token cost` | `observability` |
|---|---|---|---|---|
| Aider-AI/aider | 340 | 32 | 95 | 3 |
| cline/cline | 239 | 71 | 35 | 1 |
| langchain-ai/langchain | 225 | 53 | 37 | 26 |
| microsoft/autogen | 193 | 67 | 29 | 22 |

Issue soal context/state 10-100x lebih banyak dari issue observability. Pasar trace viewer (LangSmith, Langfuse, Phoenix, Braintrust) sudah terlayani; belum ada yang mengurus "apa yang sebenarnya dibaca agent, dan apakah masih benar".

Bukti pendukung:

- Stack Overflow Developer Survey 2025: **66%** developer bilang frustrasi terbesar AI adalah output yang "hampir benar, tapi tidak"; **45%** bilang debugging kode buatan AI lebih lama.
- Studi empiris pertanyaan agent di Stack Overflow (arXiv 2510.25423): observability cuma **11.6%** dari masalah agent, sementara koordinasi tool dan konfigurasi **23%**.
- Judul issue yang berulang di lapangan: *"Cline auto compacts context silently"*, *"Clinerules are completely ignored"*, *"Checkpoint restore fails after internal continuations"*, *"1M context capped at 128K"*.

Linter tidak bisa memperbaiki modelnya. Tapi dia bisa menghentikan kamu memberi model itu informasi palsu — gratis.

## Instalasi

Belum ada di PyPI — clone dulu:

```bash
git clone https://github.com/Mutiaacode/ctxlint
pipx install ./ctxlint          # atau: uv tool install ./ctxlint
# tidak punya pipx? jalankan langsung saja:
python3 ctxlint/ctxlint.py --help
```

Python 3.10+. Tanpa dependency. Tanpa panggilan jaringan. Tanpa API key.

## Cara pakai

```bash
ctxlint                          # periksa repo di folder sekarang
ctxlint path/to/repo             # periksa repo lain
ctxlint --agent hermes           # periksa ~/.hermes/skills + ~/.hermes/memories
ctxlint --quiet                  # hanya error (cocok untuk CI)
ctxlint --json                   # output mesin (cocok untuk script/editor)
ctxlint --ignore stale,cost      # lewati aturan yang berisik
ctxlint --max-tokens 6000        # budget token per file (default 4000)
ctxlint --max-days 90            # ambang basi lewat git (default 180)
ctxlint --selftest               # jalankan assertion bawaan
```

Matikan satu baris tertentu dengan komentar di ujungnya:

```markdown
- Config ada di `config/app.yaml` <!-- ctxlint-ignore -->
```

## Yang diperiksa

| code | level | arti |
|---|---|---|
| `broken-ref` | error | path yang diklaim ikut tool (`references/x.md`, `scripts/y.py`) tidak ada |
| `broken-ref` | info | path lepas/kontekstual tidak ditemukan — bisa jadi cuma contoh di teks |
| `duplicate` | warn | aturan yang sama ditulis di lebih dari satu file |
| `stale` | warn | file tidak berubah N hari menurut git — pastikan masih cocok |
| `cost` | warn | file melebihi budget token per run |
| `trigger` | info | `description` skill tidak diawali "Use when ..." — pemicunya ambigu |
| `pruned` | error | placeholder `[SKILL_PRUNED]` tertinggal di isi skill |
| `budget` | warn | file memori melewati batas karakter, tidak ada ruang untuk fakta baru |

Severity dikalibrasi berdasarkan keyakinan: hanya path yang diklaim *ikut* tool yang dianggap error. `package.json` yang disebut di tengah kalimat itu prosa, bukan cacat.

## Kompatibel dengan

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
        with: { fetch-depth: 0 }   # kedalaman git untuk cek basi
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: python3 ctxlint.py --quiet .
```

## Manfaat

- **Lebih sedikit run terbuang.** Referensi rusak adalah instruksi salah yang langsung ditaati agent. Perbaikannya paling murah: ditangkap linter, bukan setelah task gagal.
- **Prompt lebih murah.** File konteks dikirim ulang di setiap request. Memotong 7k token aturan basi dari task 5 request itu uang nyata, setiap hari.
- **Satu repo, banyak agent.** Lima agent membaca lima file aturan berbeda. `duplicate` menunjukkan aturan mana yang sudah bercabang, jadi kamu perbaiki sumbernya, bukan gejalanya.

## Prinsip desain

- Tanpa panggilan model, tanpa jaringan, tanpa telemetri — jalan di sandbox dan di CI.
- Tanpa dependency, satu file, stdlib saja.
- Bentuk yang familiar (seperti `eslint`/`ruff`): output tabel, kode aturan, `--ignore`, exit code.
- Aturan harus fakta yang bisa diperiksa, bukan selera. Yang subjektif keluar sebagai `info`.

## Roadmap / non-goals

Direncanakan: `--fix` untuk penulisan ulang yang aman (pindahkan aturan dobel ke satu file), mode `ctxsync` yang menghasilkan satu file aturan kanonik untuk semua agent, pemeriksaan config MCP (server dobel, command mati), output SARIF, pemindaian secret, dan deteksi konflik (dua skill memberi perintah berlawanan).

Tidak direncanakan: trace viewer lagi, platform eval, dashboard, framework.

## Kontribusi

Setiap aturan adalah satu fungsi di `ctxlint.py`: terima `CtxFile`, kembalikan `Finding`. Tambahkan ke `analyze()`, tambahkan fixture ke `--selftest`, lalu jalankan:

```bash
python3 ctxlint.py --selftest
```

Kalibrasi setiap aturan baru ke korpus nyata yang besar dulu. Aturan yang menyala di repo sehat lebih buruk daripada tidak ada aturan.

## Lisensi

MIT. Dibuat oleh [mutiadev](https://github.com/Mutiaacode).

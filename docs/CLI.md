# CLI

The repository includes a single CLI entrypoint:

```bash
python tools/nd_cli.py --help
```

All CLI commands read data directly from `data/` and handle compressed files (`.json.gz`, `.jsonl.gz`).

Notes:
- The CLI does **not** convert rōmaji to kana.
- Search can operate on **surface** (written forms) and/or **reading** (kana readings). Use `--mode auto` for a sensible default.

## Search (search-as-you-type)

Words (katakana input; `auto` will also try kana-normalized variants):

```bash
python tools/nd_cli.py search タクシー --domain words --mode auto --limit 5
```

Output:

```text
[word] たくしー -> タクシー【タクシー】 id=1076190 
[word] たくしー数 -> タクシー数【タクシーすう】 id=2864895 
[word] たくしー代 -> タクシー代【タクシーだい】 id=2846182 
[word] たくしー乗場 -> タクシー乗り場【タクシーのりば】 id=1076210 
[word] たくしーんぐ -> タキシング【タキシング】 id=2846546
```

Proper names:

```bash
python tools/nd_cli.py search さとう --domain names --mode auto --limit 5
```

Output:

```text
[name] さとう -> 左東【さとう】 id=5303334 Satou
[name] さとう -> 左刀【さとう】 id=5303333 Satou
[name] さとう -> 左登【さとう】 id=5303325 Satou
[name] さとう -> 佐籐【さとう】 id=5302359 Satou
[name] さとう -> 佐當【さとう】 id=5302357 Satou
```

JSON output (optionally attach cards via `--details`):

```bash
python tools/nd_cli.py search ねこ --domain words --mode auto --limit 3 --format json
```

## Word card

Exact lookup (English gloss):

```bash
python tools/nd_cli.py word --query 猫 --lang en --limit 1
```

Output (truncated):

```json
[
  {
    "id": 1467640,
    "primary": {
      "written": "猫",
      "reading": "ねこ"
    },
    "forms": {
      "kanji": [
        "猫"
      ],
      "kana": [
        "ねこ",
        "ネコ"
      ]
    },
    "priority": {
      "tags": [
        "ichi1",
        "news1",
        "nf07"
      ],
      "score": 100,
      "common": true
    },
    "education": {
      "min_grade": null
    },
    "senses": [
      {
        "id": "w1467640-s1",
        "pos": [
          "noun (common) (futsuumeis
```

## Kanji card

```bash
python tools/nd_cli.py kanji 日
```

Output (truncated):

```json
{
  "id": "U+65E5",
  "literal": "日",
  "strokes": 4,
  "radical": {
    "classical": 72
  },
  "readings": {
    "onyomi": [
      "ニチ",
      "ジツ"
    ],
    "kunyomi": [
      "ひ",
      "-び",
      "-か"
    ],
    "nanori": [
      "あ",
      "あき",
      "いる",
      "く",
      "くさ",
      "こう",
      "す",
      "たち",
      "に",
      "にっ",
      "につ",
      "へ"
    ]
  },
  "education": {
    "section": "primary",
    "grade": 1,
    "order_overall": 66,
    "order_in_grade": 66
  },
  "misc
```

## Kana card

```bash
python tools/nd_cli.py kana あ
```

Output:

```json
{
  "symbol": "あ",
  "script": "hiragana",
  "category": "seion",
  "base": "あ",
  "diacritic": null,
  "combo": null,
  "gojuon_row": 0,
  "gojuon_col": 0,
  "romaji": "a",
  "notes": {
    "it": null
  }
}
```

## Categories (Drops-like)

List categories (English):

```bash
python tools/nd_cli.py category list --lang en --limit 3
```

Output (truncated):

```json
[
  {
    "id": "grammar_particles",
    "title": "Particles & basic grammar",
    "description": "Particles, auxiliary forms, and other high-frequency grammar items."
  },
  {
    "id": "questions",
    "title": "Question words",
    "description": "Question words and interrogative expressions."
  },
  {
    "id": "pronouns",
    "title": "Pronouns & people",
    "description": "Personal pronouns and common people-references."
  },
  {
    "id": "greetings",
    "title": "Greetings & polite phr
```

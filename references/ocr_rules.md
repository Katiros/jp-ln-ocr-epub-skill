# OCR Rules

## Page Classification

Classify every image before OCR:

- `cover`: front cover or title cover.
- `illustration`: mostly image, little or no body text.
- `body`: vertical novel prose.
- `toc`: table of contents.
- `copyright`: copyright/colophon page.
- `blank`: near-empty page.
- `unknown`: uncertain; keep for manual review.

Illustration pages should be preserved in the manifest and EPUB image assets, even when skipped for OCR.

Use OCR-derived page metrics after detection:

- `text_density`: total detected text box area divided by page area.
- `box_count`: number of detected text boxes.
- `char_count`: recognized text length.
- `mean_confidence`: average recognition score.

Suggested first-pass rules:

- Very low `text_density` and low `box_count` -> `blank` or `illustration`.
- Low `box_count` with short text -> `chapter`.
- Medium/high `text_density` -> `body`.
- Named cover/insert files override metrics, but keep low-confidence classifications in the report.

## Vertical Reading Order

Japanese vertical novel pages are read:

1. Top-to-bottom within a column.
2. Right-to-left across columns.
3. Page-to-page in natural filename order unless the manifest overrides it.

Never concatenate OCR boxes by left-to-right order.

## Ruby/Furigana

Ruby text is small text beside main vertical text. Treat it as metadata unless it changes meaning.

Remove ordinary pronunciation ruby from body text:

```text
上条当麻 with ruby かみじょうとうま -> 上条当麻
```

Preserve special ruby in glossary:

```text
魔神 with ruby ネフテュス -> glossary: 魔神 / ネフテュス
```

If OCR merges ruby into text, repair or flag:

```text
Bad: 上かみ条じょう当とう麻ま
Good: 上条当麻
Glossary: 上条当麻 / かみじょうとうま
```

For v0.2, ruby handling is conservative:

- Keep raw OCR lines available.
- Flag likely contamination instead of rewriting aggressively.
- Extract obvious base/ruby pairs only when the source is unambiguous.
- Require review for special readings and name readings.

Future dedicated script target:

```text
detect_ruby.py
  input: OCR lines with boxes
  output: body lines + ruby_pairs.json
```

The target ruby pair format is:

```json
{"base": "上条", "ruby": "かみじょう", "type": "person_name", "page": 12}
```

## Section Markers

Do not blindly remove isolated digits.

- Isolated digit near a page corner -> likely page number.
- Isolated digit in the text flow, surrounded by whitespace, before new prose -> section marker.
- Preserve section markers as their own paragraph or Markdown heading.

Example:

```text
電車は走る。
この小さな綻びから再出発だ。

## 2

上条当麻やアリス＝アナザーバイブル達は去った。
```

## Glossary Candidates

Extract likely terms before translation:

- Kanji person names with known ruby.
- Katakana names.
- Names or titles joined by `=`, `＝`, `・`, or long compounds.
- Quoted special labels such as `「魔神」`.

Write candidates for user confirmation, not as final translations.

## Cleanup

Remove:

- Isolated page numbers.
- Page headers and footers.
- OCR noise outside text columns.
- Duplicate fragments caused by ruby.

Preserve:

- Japanese dialogue quotes before translation.
- Long ellipses and hesitant dialogue rhythm.
- Chapter titles and section breaks.
- Uncertain text markers.

## Paragraph Repair

Merge page breaks when:

- Previous text has no sentence-ending punctuation.
- Dialogue quote is unclosed.
- The next page starts with continuation punctuation or continuation grammar.

Do not merge when:

- A new chapter title starts.
- The next page is illustration/title/blank.
- There is an explicit scene break.

## Review-First Rule

Stop after producing `03_ordered_jp` and `logs/quality_report.md`.

Do not translate directly from raw OCR unless the user explicitly requests a draft. The user should be able to fix:

- page type mistakes
- ruby merged into body text
- missing or duplicated columns
- page numbers in body text
- chapter split mistakes
- low-confidence pages

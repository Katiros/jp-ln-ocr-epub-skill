# Translation Style

Translate into natural Simplified Chinese light-novel prose.

## Principles

- Preserve the author's pacing, especially ellipses, hesitation, and abrupt dialogue.
- Keep paragraph breaks unless OCR reconstruction clearly broke them.
- Maintain consistent names, titles, organizations, magic/technical terms, and nicknames.
- Translate honorifics by meaning and relationship, not mechanically.
- Avoid stiff literal translation, but do not rewrite plot facts.
- Mark uncertain OCR as `[OCR疑问: 原文片段]`.

## DeepSeek Usage

Use `DEEPSEEK_API_KEY` from the environment. Translate by paragraph or small scene chunks, not isolated pages.

Include:

- Current glossary.
- Previous 1-3 paragraphs or a chapter summary.
- OCR uncertainty notes.
- The current Japanese source chunk.

Require output sections:

```text
## Translation
...

## Glossary Updates
- 原文 | 读音/ルビ | 中文译名 | 类型 | 备注

## OCR Notes
- ...
```

## Glossary Format

Use YAML:

```yaml
entries:
  - source: 上条当麻
    reading: かみじょうとうま
    zh: 上条当麻
    type: person
    note: fixed published/common rendering
  - source: 魔神
    reading: ネフテュス
    zh: 魔神奈芙蒂斯
    type: title/person
    note: ruby identifies the named speaker/entity
```


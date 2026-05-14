# EPUB Rules

## Template Reuse

When a template EPUB is provided:

- Preserve CSS files unless the user asks for restyling.
- Preserve embedded fonts and font-face declarations.
- Preserve cover conventions when compatible.
- Preserve useful metadata structure, but update title, author, language, identifier, and date.
- Replace body XHTML with generated chapter XHTML.

## Packaging

EPUB zip rules:

- `mimetype` must be the first ZIP entry.
- `mimetype` must be stored uncompressed.
- Other files may be compressed.
- `META-INF/container.xml` must point to the OPF file.
- OPF manifest, spine, and nav/NCX must reference existing files.

## Chapter XHTML

Generate one XHTML file per chapter unless the template requires another split strategy.

Use semantic structure:

```html
<section class="chapter">
  <h1>...</h1>
  <p>...</p>
</section>
```

Keep illustration references as image blocks and preserve image assets in the EPUB package.


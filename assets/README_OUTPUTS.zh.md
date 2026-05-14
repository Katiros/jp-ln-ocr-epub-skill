# 输出目录说明

这是一个“先审阅、后翻译、最后制作 EPUB”的工作目录。推荐处理顺序是：

```text
扫描目录 -> OCR -> 竖排排序日文 -> 清洗日文 -> Word 审阅
-> 翻译 -> Word 审阅译文 -> 最后制作 EPUB
```

## 优先打开哪些文件

- `chapters/ch001_ocr.docx`  
  第一章 OCR 日文稿，用于人工校对 OCR。

- `chapters/ch001_zh.docx`  
  第一章中文译文稿，用于人工校对翻译。如果还没有配置 DeepSeek API，可能只是样稿或摘录。

- `chapters/ch001_bilingual.docx`  
  日文 OCR 与中文译文合并的双语 Word，适合对照审阅。

## 各目录用途

- `00_manifest/manifest.json`  
  图片页序、页面类型、OCR 状态、置信度和生成文件路径。

- `00_manifest/chapter_boundaries.json`  
  自动检测出的章节起点和页码范围。

- `02_ocr_raw/`  
  PaddleOCR 的紧凑 JSON 输出。保留文字、置信度和坐标，用于排查 OCR、ruby 和版面问题。

- `03_ordered_jp/`  
  每页按竖排从右到左恢复后的日文文本。适合检查某一页的阅读顺序。

- `04_cleaned_jp/`  
  保守清洗后的日文文本。章节合并稿也放在这里。

- `05_glossary/glossary_candidates.csv`  
  自动抽取的人名/术语候选。需要人工确认后才能用于强制统一译名。

- `06_translated_zh/`  
  中文译文输出。

- `chapters/`  
  给人审阅的 Word 文件。通常优先看这个目录。

- `logs/quality_report.md`  
  OCR 低置信度页和需要人工检查的页面。

- `logs/cleanup_warnings.md`  
  清洗阶段发现的疑似 ruby 混入、异常 OCR 行等问题。

## 当前阶段提醒

- Word 文件是审阅用交付件。
- EPUB 应该等 OCR 和翻译都审阅完成后再制作。
- 自动抽取的术语表只是候选，不应直接当作最终译名表。


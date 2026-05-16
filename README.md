# JP LN OCR EPUB Skill

这是一个面向 **竖排日文轻小说扫图** 的 Codex / OpenClaw skill。

目标不是“一键直接出 EPUB”，而是按更适合校对的顺序处理：

```text
扫图文件夹
-> PaddleOCR
-> 竖排阅读顺序恢复
-> OCR Word 审阅
-> DeepSeek 翻译
-> 翻译 Word 审阅
-> 最后制作 EPUB
```

也就是说，EPUB 是最后的包装步骤。OCR 和翻译没有审完之前，不建议直接生成 EPUB。

## 第一次使用

### 1. 安装依赖

Windows + NVIDIA GPU + CUDA 13.0：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1 -Mode gpu-cu130
```

没有 GPU，或 GPU 环境装不起来时：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1 -Mode cpu
```

如果你的 Python 不在 PATH，可以显式指定：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1 `
  -Mode gpu-cu130 `
  -PythonPath "C:/Path/To/python.exe"
```

安装脚本会自动：

- 创建 `.venv`
- 安装 PaddlePaddle / PaddleOCR
- 安装 Word 导出依赖 `python-docx`
- 安装 `Pillow`、`PyYAML`
- 默认使用清华 PyPI 镜像
- 检查 PaddleOCR 环境

默认会把运行环境和缓存都放在 skill 目录下：

```text
.venv/              Python 虚拟环境
.cache/wheels/      Paddle wheel 下载缓存
.cache/paddle/      Paddle 缓存
.cache/paddleocr/   PaddleOCR 缓存
.cache/paddlex/     PaddleX/官方 OCR 模型缓存
.cache/pip/         pip 缓存
```

Codex 和 OpenClaw 在同一台机器上使用时，建议都调用同一个解释器：

```text
.\.venv\Scripts\python.exe
```

这样不需要分别安装两套 PaddleOCR 环境。清理时删除 `.venv/` 和 `.cache/` 即可。

### 2. 复制配置文件

不要直接改 `assets/config.example.yaml`。请复制一份到仓库根目录：

```powershell
Copy-Item assets\config.example.yaml config.yaml
```

然后编辑：

```text
config.yaml
```

`config.yaml` 已经在 `.gitignore` 里，不会被提交到 GitHub。

## 必须配置哪些内容

打开 `config.yaml`，通常只需要先改这几块。

### 输入目录

```yaml
input:
  path: "C:/Users/Katiros/Desktop/EPUB/創約12/扫图"
```

这里填整本轻小说图片所在文件夹。

### 输出目录

```yaml
output:
  dir: "G:/code/novel-output/souyaku12"
```

所有 OCR、Word、日志、术语表都会输出到这里。

### OCR 设备

GPU：

```yaml
ocr:
  device: gpu
```

CPU：

```yaml
ocr:
  device: cpu
```

### DeepSeek API

配置文件默认读取环境变量：

```yaml
translation:
  api_key_env: DEEPSEEK_API_KEY
```

使用前设置：

```powershell
$env:DEEPSEEK_API_KEY="你的 DeepSeek API Key"
```

如果只是 OCR 和 Word 审阅，暂时不需要配置 DeepSeek。

### EPUB 模板

EPUB 阶段还在后面。以后要做 EPUB 时再填：

```yaml
epub:
  template: "C:/path/to/template.epub"
```

## 推荐运行顺序

下面假设你已经复制并编辑了 `config.yaml`。

### 1. 扫描图片目录

```powershell
.\.venv\Scripts\python.exe scripts\book_pipeline.py scan --config config.yaml
```

会生成：

```text
输出目录/00_manifest/manifest.json
```

它记录每张图片的顺序、页面类型、OCR 状态等。

### 2. OCR 指定页码范围

例如只跑第 12 到 60 页：

```powershell
.\.venv\Scripts\python.exe scripts\ocr_paddle_book.py --config config.yaml --start-page 12 --end-page 60
```

会生成：

```text
02_ocr_raw/      OCR 紧凑 JSON
03_ordered_jp/   竖排排序后的每页日文
logs/quality_report.md
```

### 3. 清洗 OCR 并抽取术语候选

把下面命令里的 `输出目录` 换成你 `config.yaml` 里的 `output.dir`。

```powershell
.\.venv\Scripts\python.exe scripts\clean_ocr_japanese.py `
  --input-dir 输出目录\03_ordered_jp `
  --output-dir 输出目录\04_cleaned_jp `
  --glossary-csv 输出目录\05_glossary\glossary_candidates.csv `
  --warnings-md 输出目录\logs\cleanup_warnings.md
```

会生成：

```text
04_cleaned_jp/                         清洗后的日文
05_glossary/glossary_candidates.csv     术语候选
logs/cleanup_warnings.md                疑似 ruby 混入/异常行警告
```

### 4. 检测章节边界

```powershell
.\.venv\Scripts\python.exe scripts\detect_chapters.py `
  --input-dir 输出目录\04_cleaned_jp `
  --output 输出目录\00_manifest\chapter_boundaries.json
```

用于判断：

```text
第一章从哪一页开始
第二章从哪一页开始
某章应该包含哪些页
```

### 4.5. 从 wiki 预填术语候选

如果目标作品有 wiki，可以先用 OCR 抽出的术语候选去 wiki 搜索，减少人工确认量。默认脚本指向《魔法禁书目录》灰机 wiki 的 MediaWiki API：

```powershell
.\.venv\Scripts\python.exe scripts\import_wiki_glossary.py `
  --terms-csv 输出目录\05_glossary\glossary_candidates.csv `
  --output 输出目录\05_glossary\wiki_glossary_candidates.csv
```

生成的 `wiki_glossary_candidates.csv` 仍然需要人工确认，不会直接覆盖你的术语表。

如果 wiki API 返回 `403 Forbidden`，可以在浏览器里手动整理/导出一份 CSV，再用：

```powershell
.\.venv\Scripts\python.exe scripts\import_wiki_glossary.py `
  --manual-csv 手动整理的wiki术语.csv `
  --output 输出目录\05_glossary\wiki_glossary_candidates.csv
```

手动 CSV 至少包含这些列之一即可：

```text
source,reading,zh
```

或：

```text
日文,假名,中文
```

如果连 CSV 都懒得整理，也可以把浏览器里能打开的 wiki 页面复制到一个文本文件，例如：

```text
G:/code/wiki_seed/toaru_terms.txt
```

然后离线导入：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_windows.ps1 `
  -Step import-wiki-glossary `
  -OutputDir 输出目录 `
  -ManualWikiText G:/code/wiki_seed/toaru_terms.txt
```

`--manual-text` 支持几种松散格式：

```text
日文名：上条当麻
假名：かみじょうとうま
中文名：上条当麻

アリス＝アナザーバイブル	爱丽丝＝另一圣经
ネフテュス => 奈芙蒂斯
```

这条路线会自动使用离线模式，不走灰机 wiki API，所以不会被 Cloudflare 的自动化拦截影响。导入结果仍然是 `pending_review`，需要你最后确认。

### 4.6. 生成初版术语表

不需要从空白表开始手填。可以让 skill 先把 OCR 候选、wiki 候选、已有术语表合并成一份初版：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_windows.ps1 `
  -Step draft-glossary `
  -OutputDir 输出目录
```

会生成：

```text
05_glossary/glossary_draft.csv
```

如果你有以前翻译组整理过的术语表，可以作为种子表传进去：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_windows.ps1 `
  -Step draft-glossary `
  -OutputDir 输出目录 `
  -SeedGlossary G:/code/wiki_seed/confirmed_terms.csv
```

如果你已经配置了 `DEEPSEEK_API_KEY`，也可以让 DeepSeek 给缺译名的项目生成草案：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_windows.ps1 `
  -Step draft-glossary `
  -OutputDir 输出目录 `
  -UseDeepSeekGlossaryDraft
```

生成规则：

- wiki/种子表匹配到的译名会优先填入。
- 纯汉字人名/术语会先按中文汉字原样填入，标记为 `draft`。
- 片假名、外来语、复杂专名如果没有来源，会保留为 `pending_review`；开启 DeepSeek 后会尝试补草案。
- 自动生成的内容不会标记为 `confirmed`，需要你复核后手动确认。

### 4.7. 生成翻译用术语表

正式翻译不要直接使用 `glossary_candidates.csv` 或整份 `glossary_draft.csv`。先生成过滤后的翻译用术语表：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_windows.ps1 `
  -Step build-translation-glossary `
  -OutputDir 输出目录
```

会生成：

```text
05_glossary/glossary_for_translation.txt
05_glossary/glossary_for_translation_rejected.csv
```

默认规则：

- `confirmed` 一定进入翻译用术语表。
- `draft` 只有中高置信度才进入。
- `pending_review`、`remove`、`rejected` 不进入。
- 疑似 OCR 碎片、过短、过长、含空白或边界标点的条目不进入。
- 默认排除超过 28 个字符的 source，减少多个词粘在一起的 OCR 长串进入 prompt。
- 默认会检查 `アリス`、`アンナ`、`コロンゾン`、`上条` 这类常见独立专名是否被粘到前一个词后面；疑似粘连的条目不进入。

`glossary_for_translation.txt` 的格式是：

```text
一方通行 → 一方通行
アリス＝アナザーバイブル → 爱丽丝＝异典
```

DeepSeek 会把它当译名参考，不是字符串替换。翻译 prompt 会提醒模型：如果某条术语明显不是当前上下文里的独立词，就忽略。

翻译时优先把这份文件传给 `--glossary`：

```powershell
.\.venv\Scripts\python.exe scripts\deepseek_translate.py `
  --input 输出目录\04_cleaned_jp\chapter_01.jp.md `
  --output 输出目录\06_translated_zh\chapter_01.zh.md `
  --glossary 输出目录\05_glossary\glossary_for_translation.txt
```

### 5. 生成中文输出说明

```powershell
.\.venv\Scripts\python.exe scripts\write_output_readme.py --output-dir 输出目录
```

会生成：

```text
README_OUTPUTS.md
```

这份文件是中文的，会解释输出目录里每个文件夹的作用。

### 6. 导出 Word 审阅文件

示例：

```powershell
.\.venv\Scripts\python.exe scripts\export_docx_chapter.py `
  --title "第一章 白与黑的景色中" `
  --jp 输出目录\04_cleaned_jp\chapter_01.jp.md `
  --zh 输出目录\06_translated_zh\chapter_01.zh.md `
  --output-dir 输出目录\chapters `
  --prefix ch001
```

会生成：

```text
chapters/ch001_ocr.docx
chapters/ch001_zh.docx
chapters/ch001_bilingual.docx
```

如果还没有中文译文，可以先只导出 OCR Word，用来校对日文。

### 7. 生成“人工复核中心”

```powershell
.\.venv\Scripts\python.exe scripts\build_review_pack.py --output-dir 输出目录
```

会生成：

```text
08_review/
  README_REVIEW.md
  low_confidence_pages.md
  cleanup_warnings.md
  glossary_candidates.csv
  chapter_boundaries_review.md
  docx_review_index.md
```

之后人工审阅时，优先打开：

```text
08_review/README_REVIEW.md
```

### 8. 一键生成第一章 OCR 审阅包

如果是让 OpenClaw 或其他 agent 调用，优先使用这个封装步骤，避免它只跑一半流程：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_windows.ps1 `
  -Step first-chapter-review `
  -Config config.yaml `
  -OutputDir 输出目录 `
  -StartPage 12 `
  -EndPage 60 `
  -Chapter 1
```

这个步骤会自动执行：

```text
scan -> OCR -> clean -> detect-chapters -> draft glossary -> translation glossary -> merge chapter -> export DOCX -> README_OUTPUTS -> 08_review -> cleanup
```

它默认只生成 OCR 审阅稿，不会调用 DeepSeek 翻译，也不会制作 EPUB。

### 9. 清理临时缓存

普通运行结束后可以执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_windows.ps1 `
  -Step cleanup `
  -OutputDir 输出目录
```

会清理：

- 输出目录里的 `temp/`、`tmp/`、`__pycache__/`、`.tmp` 文件
- skill 目录下 `.cache/paddlex/temp`
- PaddleX 模型目录里残留的 `._____temp`
- `scripts/__pycache__`

不会清理：

- `02_ocr_raw/`
- `03_ordered_jp/`
- `04_cleaned_jp/`
- `05_glossary/`
- `08_review/`
- `chapters/`
- `.venv/`
- 已下载的 OCR 模型

如果你想连 `.venv` 里的 Python 编译缓存也清掉，可以加：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_windows.ps1 `
  -Step cleanup `
  -OutputDir 输出目录 `
  -IncludeVenvPycache
```

这会释放一些空间，但下次启动 Python 包时可能会稍慢。

## 输出目录怎么看

默认会按阶段放文件：

```text
00_manifest/       页序、章节边界、处理状态
02_ocr_raw/        PaddleOCR 紧凑 JSON
03_ordered_jp/     按竖排顺序恢复后的每页日文
04_cleaned_jp/     清洗后的日文和章节合并稿
05_glossary/       术语候选/术语表
06_translated_zh/  中文译文
08_review/         人工复核中心
chapters/          Word 审阅文件
logs/              质量报告和警告
```

普通审阅时，优先看：

```text
08_review/
chapters/
README_OUTPUTS.md
logs/quality_report.md
logs/cleanup_warnings.md
```

## 不会提交到 GitHub 的文件

下面这些已经写进 `.gitignore`：

```text
config.yaml
.env
.venv/
.cache/
output/
outputs/
workspace/
02_ocr_raw/
03_ordered_jp/
04_cleaned_jp/
05_glossary/
06_translated_zh/
08_review/
chapters/
logs/
*.whl
official_models/
```

所以你的真实配置、API Key、OCR 输出、Word 文件、EPUB 工作目录不会被提交。

仓库里只保留示例配置：

```text
assets/config.example.yaml
```

## 当前能力边界

已经可用：

- 扫描整本图片文件夹
- PaddleOCR 批量识别
- 竖排从右到左排序
- 生成 OCR 质量报告
- 章节边界检测
- 术语候选抽取
- 从 MediaWiki wiki 预填术语候选
- Word 审阅文件导出
- 中文输出说明生成

仍需继续完善：

- ruby / 振假名精准剥离
- 复杂人物介绍页、彩页说明页分类
- 更自然的段落合并
- EPUB 自动制作

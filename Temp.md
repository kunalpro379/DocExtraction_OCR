import sys
import json
import os
import csv
import io
import argparse

from ADI import analyze_pdf
from Extraction import extract_from_adi_json, extract_from_raw_json

INPUT_DIR     = "Input"
OUTPUT_DIR    = "output"
EXTRACTED_DIR = "Extracted"
OUTPUT_RAW_DIR = "OutputRaw"


# ── Report builders ───────────────────────────────────────────────────────────

def build_markdown_report(name: str, extracted: dict, adi_dict: dict = None) -> str:
    lines = [f"# {name}", "", "## Extracted Fields", ""]
    for k, v in extracted.items():
        if k in ("created_at", "updated_at", "id"):
            continue
        display = v if v is not None else "_null_"
        lines.append(f"- **{k}**: {display}")

    if adi_dict:
        ar     = adi_dict.get("analyzeResult", {})
        tables = ar.get("tables", [])
        if tables:
            lines += ["", "---", "", "## Tables", ""]
            for ti, table in enumerate(tables):
                lines.append(f"### Table {ti+1} ({table.get('rowCount')}r × {table.get('columnCount')}c)")
                lines.append("")
                cells = table.get("cells", [])
                grid  = {}
                for cell in cells:
                    r, c = cell.get("rowIndex", 0), cell.get("columnIndex", 0)
                    grid[(r, c)] = cell.get("content", "").replace("\n", " ")
                if grid:
                    rows = max(r for r, _ in grid) + 1
                    cols = max(c for _, c in grid) + 1
                    header = "| " + " | ".join(grid.get((0, c), "") for c in range(cols)) + " |"
                    sep    = "| " + " | ".join("---" for _ in range(cols)) + " |"
                    lines += [header, sep]
                    for r in range(1, rows):
                        lines.append("| " + " | ".join(grid.get((r, c), "") for c in range(cols)) + " |")
                lines.append("")

        content = ar.get("content", "")
        if content:
            lines += ["", "---", "", "## Full Document Text", "", "```"]
            lines += content.splitlines()
            lines.append("```")

    return "\n".join(lines)


def build_txt_report(extracted: dict, adi_dict: dict = None) -> str:
    content = ""
    if adi_dict:
        content = adi_dict.get("analyzeResult", {}).get("content", "")
    lines = ["=" * 60, "EXTRACTED FIELDS", "=" * 60]
    for k, v in extracted.items():
        lines.append(f"{k:<45}: {v if v is not None else ''}")
    if content:
        lines += ["", "=" * 60, "FULL DOCUMENT TEXT", "=" * 60, "", content]
    return "\n".join(lines)


def build_csv(extracted: dict) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(extracted.keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerow(extracted)
    return buf.getvalue()


# ── Save helpers ──────────────────────────────────────────────────────────────

def save_all_formats(name: str, extracted: dict, adi_dict: dict = None):
    folder = os.path.join(EXTRACTED_DIR, name)
    os.makedirs(folder, exist_ok=True)

    # Save extracted JSON to OutputRaw/
    os.makedirs(OUTPUT_RAW_DIR, exist_ok=True)
    raw_out = os.path.join(OUTPUT_RAW_DIR, f"{name}_extracted.json")
    with open(raw_out, "w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2, ensure_ascii=False)
    print(f"         → {raw_out}")

    def w(path, content):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"         → {path}")

    w(os.path.join(folder, f"{name}_extracted.json"),
      json.dumps(extracted, indent=2, ensure_ascii=False))

    w(os.path.join(folder, f"{name}.txt"),
      build_txt_report(extracted, adi_dict))

    w(os.path.join(folder, f"{name}.md"),
      build_markdown_report(name, extracted, adi_dict))

    w(os.path.join(folder, f"{name}.csv"),
      build_csv(extracted))

    # Save raw ADI JSON only in full mode
    if adi_dict:
        p = os.path.join(folder, f"{name}_adi_raw.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(adi_dict, f, indent=2, ensure_ascii=False)
        print(f"         → {p}")

        ar         = adi_dict.get("analyzeResult", {})
        pages      = ar.get("pages", [])
        paragraphs = ar.get("paragraphs", [])
        tables     = ar.get("tables", [])
        content    = ar.get("content", "")

        if paragraphs:
            p = os.path.join(folder, f"{name}_paragraphs.txt")
            with open(p, "w", encoding="utf-8") as f:
                for i, para in enumerate(paragraphs):
                    role = para.get("role", "")
                    text = para.get("content", "")
                    f.write(f"[{i+1}]{f' ({role})' if role else ''} {text}\n\n")
            print(f"         → {p}")

        if pages:
            p = os.path.join(folder, f"{name}_pages.txt")
            with open(p, "w", encoding="utf-8") as f:
                for page in pages:
                    pnum  = page.get("pageNumber", "?")
                    spans = page.get("spans", [])
                    f.write(f"{'='*40}\nPAGE {pnum}\n{'='*40}\n")
                    for span in spans:
                        offset = span.get("offset", 0)
                        length = span.get("length", 0)
                        f.write(content[offset: offset + length])
                    f.write("\n\n")
            print(f"         → {p}")

        for ti, table in enumerate(tables):
            cells = table.get("cells", [])
            grid  = {}
            for cell in cells:
                r, c = cell.get("rowIndex", 0), cell.get("columnIndex", 0)
                grid[(r, c)] = cell.get("content", "").replace("\n", " ")
            if not grid:
                continue
            rows = max(r for r, _ in grid) + 1
            cols = max(c for _, c in grid) + 1
            p = os.path.join(folder, f"{name}_table_{ti+1}.csv")
            with open(p, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                for r in range(rows):
                    writer.writerow([grid.get((r, c), "") for c in range(cols)])
            print(f"         → {p}")


# ── Processing modes ──────────────────────────────────────────────────────────

def process_full(pdf_path: str) -> bool:
    """Full mode: call ADI on PDF then extract."""
    name = os.path.splitext(os.path.basename(pdf_path))[0]
    print(f"\n{'─'*50}")
    print(f"[full] {pdf_path}")
    try:
        print("  [1/3] Running ADI...")
        adi_dict = analyze_pdf(pdf_path)

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(os.path.join(OUTPUT_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(adi_dict, f, indent=2, ensure_ascii=False)

        print("  [2/3] Extracting fields...")
        extracted = extract_from_adi_json(adi_dict)

        print("  [3/3] Saving all formats...")
        save_all_formats(name, extracted, adi_dict)
        return True
    except Exception as ex:
        print(f"  [ERROR] {ex}")
        return False


def process_extract(name: str) -> bool:
    """
    Extract-only mode: read the saved _adi_raw.json from Extracted/<name>/
    and re-run extraction with the new field set.
    """
    folder       = os.path.join(EXTRACTED_DIR, name)
    raw_json_path = os.path.join(folder, f"{name}_adi_raw.json")

    # Fall back to plain text if no raw JSON
    txt_path = os.path.join(folder, f"{name}.txt")

    print(f"\n{'─'*50}")
    print(f"[extract] {name}")

    try:
        if os.path.exists(raw_json_path):
            print(f"  Reading {raw_json_path}")
            with open(raw_json_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            extracted = extract_from_raw_json(raw)
            save_all_formats(name, extracted, raw)
        elif os.path.exists(txt_path):
            print(f"  No raw JSON found, reading {txt_path}")
            with open(txt_path, "r", encoding="utf-8") as f:
                text = f.read()
            from Extraction import extract_from_text
            extracted = extract_from_text(text)
            save_all_formats(name, extracted)
        else:
            print(f"  [ERROR] No data found in {folder}")
            return False
        return True
    except Exception as ex:
        import traceback
        print(f"  [ERROR] {ex}")
        traceback.print_exc()
        return False


# ── Batch runners ─────────────────────────────────────────────────────────────

def run_full_batch():
    if not os.path.isdir(INPUT_DIR):
        print(f"[ERROR] Folder '{INPUT_DIR}' not found.")
        sys.exit(1)
    pdfs = sorted(
        os.path.join(INPUT_DIR, f)
        for f in os.listdir(INPUT_DIR)
        if f.lower().endswith(".pdf")
    )
    if not pdfs:
        print(f"[ERROR] No PDFs in '{INPUT_DIR}/'")
        sys.exit(1)

    print(f"Found {len(pdfs)} PDF(s) — running full mode (ADI + extract)")
    ok, fail = 0, []
    for pdf in pdfs:
        if process_full(pdf):
            ok += 1
        else:
            fail.append(os.path.basename(pdf))
    _print_summary(ok, fail)


def run_extract_batch():
    if not os.path.isdir(EXTRACTED_DIR):
        print(f"[ERROR] Folder '{EXTRACTED_DIR}' not found.")
        sys.exit(1)
    folders = sorted(
        d for d in os.listdir(EXTRACTED_DIR)
        if os.path.isdir(os.path.join(EXTRACTED_DIR, d))
    )
    if not folders:
        print(f"[ERROR] No sub-folders in '{EXTRACTED_DIR}/'")
        sys.exit(1)

    print(f"Found {len(folders)} folder(s) in '{EXTRACTED_DIR}/' — running extract-only mode")
    ok, fail = 0, []
    for folder_name in folders:
        if process_extract(folder_name):
            ok += 1
        else:
            fail.append(folder_name)
    _print_summary(ok, fail)


def _print_summary(ok: int, fail: list):
    print(f"\n{'='*50}")
    print(f"Done.  Success: {ok}  Failed: {len(fail)}")
    if fail:
        print(f"Failed: {', '.join(fail)}")
    print(f"{'='*50}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agreement extraction pipeline")
    parser.add_argument(
        "mode",
        choices=["full", "extract"],
        help=(
            "full    – run Azure Document Intelligence (ADI) on PDFs in Input/, "
            "then extract fields and save all outputs.\n"
            "extract – re-extract fields from already-saved ADI raw JSON in "
            "Extracted/ (no ADI API call)."
        ),
    )
    args = parser.parse_args()

    if args.mode == "full":
        run_full_batch()
    else:
        run_extract_batch()import os
import torch
from transformers import AutoModel, AutoTokenizer

model_name = 'baidu/Unlimited-OCR'

tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
model = AutoModel.from_pretrained(
    model_name,
    trust_remote_code=True,
    use_safetensors=True,
    torch_dtype=torch.bfloat16,
)
model = model.eval().cuda()

# ── Single image supports two configs: gundam or base ──
# gundam: base_size=1024, image_size=640, crop_mode=True
# base: base_size=1024, image_size=1024, crop_mode=False
model.infer(
    tokenizer,
    prompt='<image>document parsing.',
    image_file='your_image.jpg',
    output_path='your/output/dir',
    base_size=1024, image_size=640, crop_mode=True,
    max_length=32768,
    no_repeat_ngram_size=35, ngram_window=128,
    save_results=True,
)

# ── Multi page / PDF only uses base (image_size=1024) ──
model.infer_multi(
    tokenizer,
    prompt='<image>Multi page parsing.',
    image_files=['page1.png', 'page2.png', 'page3.png'],
    output_path='your/output/dir',
    image_size=1024,
    max_length=32768,
    no_repeat_ngram_size=35, ngram_window=1024,
    save_results=True,
)

# ── PDF (convert pages to images, then multi-page parsing) ──
import tempfile, fitz  # PyMuPDF

def pdf_to_images(pdf_path, dpi=300):
    doc = fitz.open(pdf_path)
    tmp_dir = tempfile.mkdtemp(prefix='pdf_ocr_')
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    paths = []
    for i, page in enumerate(doc):
        out = os.path.join(tmp_dir, f'page_{i+1:04d}.png')
        page.get_pixmap(matrix=mat).save(out)
        paths.append(out)
    doc.close()
    return paths

model.infer_multi(
    tokenizer,
    prompt='<image>Multi page parsing.',
    image_files=pdf_to_images('Agg.pdf', dpi=300),
    output_path='output',
    image_size=1024,
    max_length=32768,
    no_repeat_ngram_size=35, ngram_window=1024,
    save_results=True,
)import sys
import json
import os
import csv
import io
import argparse

from ADI import analyze_pdf
from Extraction import extract_from_adi_json, extract_from_raw_json

INPUT_DIR     = "Input"
OUTPUT_DIR    = "output"
EXTRACTED_DIR = "Extracted"
OUTPUT_RAW_DIR = "OutputRaw"


# ── Report builders ───────────────────────────────────────────────────────────

def build_markdown_report(name: str, extracted: dict, adi_dict: dict = None) -> str:
    lines = [f"# {name}", "", "## Extracted Fields", ""]
    for k, v in extracted.items():
        if k in ("created_at", "updated_at", "id"):
            continue
        display = v if v is not None else "_null_"
        lines.append(f"- **{k}**: {display}")

    if adi_dict:
        ar     = adi_dict.get("analyzeResult", {})
        tables = ar.get("tables", [])
        if tables:
            lines += ["", "---", "", "## Tables", ""]
            for ti, table in enumerate(tables):
                lines.append(f"### Table {ti+1} ({table.get('rowCount')}r × {table.get('columnCount')}c)")
                lines.append("")
                cells = table.get("cells", [])
                grid  = {}
                for cell in cells:
                    r, c = cell.get("rowIndex", 0), cell.get("columnIndex", 0)
                    grid[(r, c)] = cell.get("content", "").replace("\n", " ")
                if grid:
                    rows = max(r for r, _ in grid) + 1
                    cols = max(c for _, c in grid) + 1
                    header = "| " + " | ".join(grid.get((0, c), "") for c in range(cols)) + " |"
                    sep    = "| " + " | ".join("---" for _ in range(cols)) + " |"
                    lines += [header, sep]
                    for r in range(1, rows):
                        lines.append("| " + " | ".join(grid.get((r, c), "") for c in range(cols)) + " |")
                lines.append("")

        content = ar.get("content", "")
        if content:
            lines += ["", "---", "", "## Full Document Text", "", "```"]
            lines += content.splitlines()
            lines.append("```")

    return "\n".join(lines)


def build_txt_report(extracted: dict, adi_dict: dict = None) -> str:
    content = ""
    if adi_dict:
        content = adi_dict.get("analyzeResult", {}).get("content", "")
    lines = ["=" * 60, "EXTRACTED FIELDS", "=" * 60]
    for k, v in extracted.items():
        lines.append(f"{k:<45}: {v if v is not None else ''}")
    if content:
        lines += ["", "=" * 60, "FULL DOCUMENT TEXT", "=" * 60, "", content]
    return "\n".join(lines)


def build_csv(extracted: dict) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(extracted.keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerow(extracted)
    return buf.getvalue()


# ── Save helpers ──────────────────────────────────────────────────────────────

def save_all_formats(name: str, extracted: dict, adi_dict: dict = None):
    folder = os.path.join(EXTRACTED_DIR, name)
    os.makedirs(folder, exist_ok=True)

    # Save extracted JSON to OutputRaw/
    os.makedirs(OUTPUT_RAW_DIR, exist_ok=True)
    raw_out = os.path.join(OUTPUT_RAW_DIR, f"{name}_extracted.json")
    with open(raw_out, "w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2, ensure_ascii=False)
    print(f"         → {raw_out}")

    def w(path, content):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"         → {path}")

    w(os.path.join(folder, f"{name}_extracted.json"),
      json.dumps(extracted, indent=2, ensure_ascii=False))

    w(os.path.join(folder, f"{name}.txt"),
      build_txt_report(extracted, adi_dict))

    w(os.path.join(folder, f"{name}.md"),
      build_markdown_report(name, extracted, adi_dict))

    w(os.path.join(folder, f"{name}.csv"),
      build_csv(extracted))

    # Save raw ADI JSON only in full mode
    if adi_dict:
        p = os.path.join(folder, f"{name}_adi_raw.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(adi_dict, f, indent=2, ensure_ascii=False)
        print(f"         → {p}")

        ar         = adi_dict.get("analyzeResult", {})
        pages      = ar.get("pages", [])
        paragraphs = ar.get("paragraphs", [])
        tables     = ar.get("tables", [])
        content    = ar.get("content", "")

        if paragraphs:
            p = os.path.join(folder, f"{name}_paragraphs.txt")
            with open(p, "w", encoding="utf-8") as f:
                for i, para in enumerate(paragraphs):
                    role = para.get("role", "")
                    text = para.get("content", "")
                    f.write(f"[{i+1}]{f' ({role})' if role else ''} {text}\n\n")
            print(f"         → {p}")

        if pages:
            p = os.path.join(folder, f"{name}_pages.txt")
            with open(p, "w", encoding="utf-8") as f:
                for page in pages:
                    pnum  = page.get("pageNumber", "?")
                    spans = page.get("spans", [])
                    f.write(f"{'='*40}\nPAGE {pnum}\n{'='*40}\n")
                    for span in spans:
                        offset = span.get("offset", 0)
                        length = span.get("length", 0)
                        f.write(content[offset: offset + length])
                    f.write("\n\n")
            print(f"         → {p}")

        for ti, table in enumerate(tables):
            cells = table.get("cells", [])
            grid  = {}
            for cell in cells:
                r, c = cell.get("rowIndex", 0), cell.get("columnIndex", 0)
                grid[(r, c)] = cell.get("content", "").replace("\n", " ")
            if not grid:
                continue
            rows = max(r for r, _ in grid) + 1
            cols = max(c for _, c in grid) + 1
            p = os.path.join(folder, f"{name}_table_{ti+1}.csv")
            with open(p, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                for r in range(rows):
                    writer.writerow([grid.get((r, c), "") for c in range(cols)])
            print(f"         → {p}")


# ── Processing modes ──────────────────────────────────────────────────────────

def process_full(pdf_path: str) -> bool:
    """Full mode: call ADI on PDF then extract."""
    name = os.path.splitext(os.path.basename(pdf_path))[0]
    print(f"\n{'─'*50}")
    print(f"[full] {pdf_path}")
    try:
        print("  [1/3] Running ADI...")
        adi_dict = analyze_pdf(pdf_path)

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(os.path.join(OUTPUT_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(adi_dict, f, indent=2, ensure_ascii=False)

        print("  [2/3] Extracting fields...")
        extracted = extract_from_adi_json(adi_dict)

        print("  [3/3] Saving all formats...")
        save_all_formats(name, extracted, adi_dict)
        return True
    except Exception as ex:
        print(f"  [ERROR] {ex}")
        return False


def process_extract(name: str) -> bool:
    """
    Extract-only mode: read the saved _adi_raw.json from Extracted/<name>/
    and re-run extraction with the new field set.
    """
    folder       = os.path.join(EXTRACTED_DIR, name)
    raw_json_path = os.path.join(folder, f"{name}_adi_raw.json")

    # Fall back to plain text if no raw JSON
    txt_path = os.path.join(folder, f"{name}.txt")

    print(f"\n{'─'*50}")
    print(f"[extract] {name}")

    try:
        if os.path.exists(raw_json_path):
            print(f"  Reading {raw_json_path}")
            with open(raw_json_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            extracted = extract_from_raw_json(raw)
            save_all_formats(name, extracted, raw)
        elif os.path.exists(txt_path):
            print(f"  No raw JSON found, reading {txt_path}")
            with open(txt_path, "r", encoding="utf-8") as f:
                text = f.read()
            from Extraction import extract_from_text
            extracted = extract_from_text(text)
            save_all_formats(name, extracted)
        else:
            print(f"  [ERROR] No data found in {folder}")
            return False
        return True
    except Exception as ex:
        import traceback
        print(f"  [ERROR] {ex}")
        traceback.print_exc()
        return False


# ── Batch runners ─────────────────────────────────────────────────────────────

def run_full_batch():
    if not os.path.isdir(INPUT_DIR):
        print(f"[ERROR] Folder '{INPUT_DIR}' not found.")
        sys.exit(1)
    pdfs = sorted(
        os.path.join(INPUT_DIR, f)
        for f in os.listdir(INPUT_DIR)
        if f.lower().endswith(".pdf")
    )
    if not pdfs:
        print(f"[ERROR] No PDFs in '{INPUT_DIR}/'")
        sys.exit(1)

    print(f"Found {len(pdfs)} PDF(s) — running full mode (ADI + extract)")
    ok, fail = 0, []
    for pdf in pdfs:
        if process_full(pdf):
            ok += 1
        else:
            fail.append(os.path.basename(pdf))
    _print_summary(ok, fail)


def run_extract_batch():
    if not os.path.isdir(EXTRACTED_DIR):
        print(f"[ERROR] Folder '{EXTRACTED_DIR}' not found.")
        sys.exit(1)
    folders = sorted(
        d for d in os.listdir(EXTRACTED_DIR)
        if os.path.isdir(os.path.join(EXTRACTED_DIR, d))
    )
    if not folders:
        print(f"[ERROR] No sub-folders in '{EXTRACTED_DIR}/'")
        sys.exit(1)

    print(f"Found {len(folders)} folder(s) in '{EXTRACTED_DIR}/' — running extract-only mode")
    ok, fail = 0, []
    for folder_name in folders:
        if process_extract(folder_name):
            ok += 1
        else:
            fail.append(folder_name)
    _print_summary(ok, fail)


def _print_summary(ok: int, fail: list):
    print(f"\n{'='*50}")
    print(f"Done.  Success: {ok}  Failed: {len(fail)}")
    if fail:
        print(f"Failed: {', '.join(fail)}")
    print(f"{'='*50}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agreement extraction pipeline")
    parser.add_argument(
        "mode",
        choices=["full", "extract"],
        help=(
            "full    – run Azure Document Intelligence (ADI) on PDFs in Input/, "
            "then extract fields and save all outputs.\n"
            "extract – re-extract fields from already-saved ADI raw JSON in "
            "Extracted/ (no ADI API call)."
        ),
    )
    args = parser.parse_args()

    if args.mode == "full":
        run_full_batch()
    else:
        run_extract_batch()import sys
import json
import os
import csv
import io
import argparse

from ADI import analyze_pdf
from Extraction import extract_from_adi_json, extract_from_raw_json

INPUT_DIR     = "Input"
OUTPUT_DIR    = "output"
EXTRACTED_DIR = "Extracted"
OUTPUT_RAW_DIR = "OutputRaw"


# ── Report builders ───────────────────────────────────────────────────────────

def build_markdown_report(name: str, extracted: dict, adi_dict: dict = None) -> str:
    lines = [f"# {name}", "", "## Extracted Fields", ""]
    for k, v in extracted.items():
        if k in ("created_at", "updated_at", "id"):
            continue
        display = v if v is not None else "_null_"
        lines.append(f"- **{k}**: {display}")

    if adi_dict:
        ar     = adi_dict.get("analyzeResult", {})
        tables = ar.get("tables", [])
        if tables:
            lines += ["", "---", "", "## Tables", ""]
            for ti, table in enumerate(tables):
                lines.append(f"### Table {ti+1} ({table.get('rowCount')}r × {table.get('columnCount')}c)")
                lines.append("")
                cells = table.get("cells", [])
                grid  = {}
                for cell in cells:
                    r, c = cell.get("rowIndex", 0), cell.get("columnIndex", 0)
                    grid[(r, c)] = cell.get("content", "").replace("\n", " ")
                if grid:
                    rows = max(r for r, _ in grid) + 1
                    cols = max(c for _, c in grid) + 1
                    header = "| " + " | ".join(grid.get((0, c), "") for c in range(cols)) + " |"
                    sep    = "| " + " | ".join("---" for _ in range(cols)) + " |"
                    lines += [header, sep]
                    for r in range(1, rows):
                        lines.append("| " + " | ".join(grid.get((r, c), "") for c in range(cols)) + " |")
                lines.append("")

        content = ar.get("content", "")
        if content:
            lines += ["", "---", "", "## Full Document Text", "", "```"]
            lines += content.splitlines()
            lines.append("```")

    return "\n".join(lines)


def build_txt_report(extracted: dict, adi_dict: dict = None) -> str:
    content = ""
    if adi_dict:
        content = adi_dict.get("analyzeResult", {}).get("content", "")
    lines = ["=" * 60, "EXTRACTED FIELDS", "=" * 60]
    for k, v in extracted.items():
        lines.append(f"{k:<45}: {v if v is not None else ''}")
    if content:
        lines += ["", "=" * 60, "FULL DOCUMENT TEXT", "=" * 60, "", content]
    return "\n".join(lines)


def build_csv(extracted: dict) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(extracted.keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerow(extracted)
    return buf.getvalue()


# ── Save helpers ──────────────────────────────────────────────────────────────

def save_all_formats(name: str, extracted: dict, adi_dict: dict = None):
    folder = os.path.join(EXTRACTED_DIR, name)
    os.makedirs(folder, exist_ok=True)

    # Save extracted JSON to OutputRaw/
    os.makedirs(OUTPUT_RAW_DIR, exist_ok=True)
    raw_out = os.path.join(OUTPUT_RAW_DIR, f"{name}_extracted.json")
    with open(raw_out, "w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2, ensure_ascii=False)
    print(f"         → {raw_out}")

    def w(path, content):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"         → {path}")

    w(os.path.join(folder, f"{name}_extracted.json"),
      json.dumps(extracted, indent=2, ensure_ascii=False))

    w(os.path.join(folder, f"{name}.txt"),
      build_txt_report(extracted, adi_dict))

    w(os.path.join(folder, f"{name}.md"),
      build_markdown_report(name, extracted, adi_dict))

    w(os.path.join(folder, f"{name}.csv"),
      build_csv(extracted))

    # Save raw ADI JSON only in full mode
    if adi_dict:
        p = os.path.join(folder, f"{name}_adi_raw.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(adi_dict, f, indent=2, ensure_ascii=False)
        print(f"         → {p}")

        ar         = adi_dict.get("analyzeResult", {})
        pages      = ar.get("pages", [])
        paragraphs = ar.get("paragraphs", [])
        tables     = ar.get("tables", [])
        content    = ar.get("content", "")

        if paragraphs:
            p = os.path.join(folder, f"{name}_paragraphs.txt")
            with open(p, "w", encoding="utf-8") as f:
                for i, para in enumerate(paragraphs):
                    role = para.get("role", "")
                    text = para.get("content", "")
                    f.write(f"[{i+1}]{f' ({role})' if role else ''} {text}\n\n")
            print(f"         → {p}")

        if pages:
            p = os.path.join(folder, f"{name}_pages.txt")
            with open(p, "w", encoding="utf-8") as f:
                for page in pages:
                    pnum  = page.get("pageNumber", "?")
                    spans = page.get("spans", [])
                    f.write(f"{'='*40}\nPAGE {pnum}\n{'='*40}\n")
                    for span in spans:
                        offset = span.get("offset", 0)
                        length = span.get("length", 0)
                        f.write(content[offset: offset + length])
                    f.write("\n\n")
            print(f"         → {p}")

        for ti, table in enumerate(tables):
            cells = table.get("cells", [])
            grid  = {}
            for cell in cells:
                r, c = cell.get("rowIndex", 0), cell.get("columnIndex", 0)
                grid[(r, c)] = cell.get("content", "").replace("\n", " ")
            if not grid:
                continue
            rows = max(r for r, _ in grid) + 1
            cols = max(c for _, c in grid) + 1
            p = os.path.join(folder, f"{name}_table_{ti+1}.csv")
            with open(p, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                for r in range(rows):
                    writer.writerow([grid.get((r, c), "") for c in range(cols)])
            print(f"         → {p}")


# ── Processing modes ──────────────────────────────────────────────────────────

def process_full(pdf_path: str) -> bool:
    """Full mode: call ADI on PDF then extract."""
    name = os.path.splitext(os.path.basename(pdf_path))[0]
    print(f"\n{'─'*50}")
    print(f"[full] {pdf_path}")
    try:
        print("  [1/3] Running ADI...")
        adi_dict = analyze_pdf(pdf_path)

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(os.path.join(OUTPUT_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(adi_dict, f, indent=2, ensure_ascii=False)

        print("  [2/3] Extracting fields...")
        extracted = extract_from_adi_json(adi_dict)

        print("  [3/3] Saving all formats...")
        save_all_formats(name, extracted, adi_dict)
        return True
    except Exception as ex:
        print(f"  [ERROR] {ex}")
        return False


def process_extract(name: str) -> bool:
    """
    Extract-only mode: read the saved _adi_raw.json from Extracted/<name>/
    and re-run extraction with the new field set.
    """
    folder       = os.path.join(EXTRACTED_DIR, name)
    raw_json_path = os.path.join(folder, f"{name}_adi_raw.json")

    # Fall back to plain text if no raw JSON
    txt_path = os.path.join(folder, f"{name}.txt")

    print(f"\n{'─'*50}")
    print(f"[extract] {name}")

    try:
        if os.path.exists(raw_json_path):
            print(f"  Reading {raw_json_path}")
            with open(raw_json_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            extracted = extract_from_raw_json(raw)
            save_all_formats(name, extracted, raw)
        elif os.path.exists(txt_path):
            print(f"  No raw JSON found, reading {txt_path}")
            with open(txt_path, "r", encoding="utf-8") as f:
                text = f.read()
            from Extraction import extract_from_text
            extracted = extract_from_text(text)
            save_all_formats(name, extracted)
        else:
            print(f"  [ERROR] No data found in {folder}")
            return False
        return True
    except Exception as ex:
        import traceback
        print(f"  [ERROR] {ex}")
        traceback.print_exc()
        return False


# ── Batch runners ─────────────────────────────────────────────────────────────

def run_full_batch():
    if not os.path.isdir(INPUT_DIR):
        print(f"[ERROR] Folder '{INPUT_DIR}' not found.")
        sys.exit(1)
    pdfs = sorted(
        os.path.join(INPUT_DIR, f)
        for f in os.listdir(INPUT_DIR)
        if f.lower().endswith(".pdf")
    )
    if not pdfs:
        print(f"[ERROR] No PDFs in '{INPUT_DIR}/'")
        sys.exit(1)

    print(f"Found {len(pdfs)} PDF(s) — running full mode (ADI + extract)")
    ok, fail = 0, []
    for pdf in pdfs:
        if process_full(pdf):
            ok += 1
        else:
            fail.append(os.path.basename(pdf))
    _print_summary(ok, fail)


def run_extract_batch():
    if not os.path.isdir(EXTRACTED_DIR):
        print(f"[ERROR] Folder '{EXTRACTED_DIR}' not found.")
        sys.exit(1)
    folders = sorted(
        d for d in os.listdir(EXTRACTED_DIR)
        if os.path.isdir(os.path.join(EXTRACTED_DIR, d))
    )
    if not folders:
        print(f"[ERROR] No sub-folders in '{EXTRACTED_DIR}/'")
        sys.exit(1)

    print(f"Found {len(folders)} folder(s) in '{EXTRACTED_DIR}/' — running extract-only mode")
    ok, fail = 0, []
    for folder_name in folders:
        if process_extract(folder_name):
            ok += 1
        else:
            fail.append(folder_name)
    _print_summary(ok, fail)


def _print_summary(ok: int, fail: list):
    print(f"\n{'='*50}")
    print(f"Done.  Success: {ok}  Failed: {len(fail)}")
    if fail:
        print(f"Failed: {', '.join(fail)}")
    print(f"{'='*50}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agreement extraction pipeline")
    parser.add_argument(
        "mode",
        choices=["full", "extract"],
        help=(
            "full    – run Azure Document Intelligence (ADI) on PDFs in Input/, "
            "then extract fields and save all outputs.\n"
            "extract – re-extract fields from already-saved ADI raw JSON in "
            "Extracted/ (no ADI API call)."
        ),
    )
    args = parser.parse_args()

    if args.mode == "full":
        run_full_batch()
    else:
        run_extract_batch()import os
import shutil

SOURCE_DIR = "Agreement"   # folder with original PDFs
TARGET_DIR = "Input"       # destination folder

os.makedirs(TARGET_DIR, exist_ok=True)

pdfs = sorted([f for f in os.listdir(SOURCE_DIR) if f.lower().endswith(".pdf")])

if not pdfs:
    print(f"No PDFs found in '{SOURCE_DIR}/'")
else:
    for i, filename in enumerate(pdfs, start=1):
        new_name = f"Agmt_{i:02d}.pdf"
        src = os.path.join(SOURCE_DIR, filename)
        dst = os.path.join(TARGET_DIR, new_name)
        shutil.copy2(src, dst)
        print(f"  {filename}  →  {new_name}")

    print(f"\nDone. {len(pdfs)} PDF(s) copied to '{TARGET_DIR}/'")import os
import shutil

SOURCE_DIR = "Agreement"   # folder with original PDFs
TARGET_DIR = "Input"       # destination folder

os.makedirs(TARGET_DIR, exist_ok=True)

pdfs = sorted([f for f in os.listdir(SOURCE_DIR) if f.lower().endswith(".pdf")])

if not pdfs:
    print(f"No PDFs found in '{SOURCE_DIR}/'")
else:
    for i, filename in enumerate(pdfs, start=1):
        new_name = f"Agmt_{i:02d}.pdf"
        src = os.path.join(SOURCE_DIR, filename)
        dst = os.path.join(TARGET_DIR, new_name)
        shutil.copy2(src, dst)
        print(f"  {filename}  →  {new_name}")

    print(f"\nDone. {len(pdfs)} PDF(s) copied to '{TARGET_DIR}/'")First Party

Company Name

CIN

PAN

GSTIN

Address

Email

Phone

Authorized Signatory

DesignationSecond PartyStamp Paper DetailsCertificate Number



Unique Doc Reference



Stamp Duty Amount



Stamp Value



State



Purchased By



Purchased Date



First Party



Second Party



Description



Stamp Vendor



Account Reference

Can be



Individual

Company

LLP

Partnership

Proprietorship

HUFContract Financial InformationService Fee



Processing Fee



Loan Amount



Rent



Security Deposit



Penalty



Late Fee



Interest Rate



GST



Taxes



Commission



Percentage



Payment Frequency



Currency



Invoice Due Days



Invoice CycleExecution Date



Effective Date



Start Date



End Date



Termination Date



Renewal Date



Notice Period



Invoice Date



Payment Due Date



Board Resolution DateLegal ClausesConfidentiality



Intellectual Property



Indemnity



Termination



Force Majeure



Jurisdiction



Governing Law



Audit Rights



Liability



Insurance



Compliance



Data Privacy



Arbitration



Non Solicitation



Non Compete



Code of Conduct



Business Continuity



Subcontracting



Assignment



Representations



Warranties



Entire Agreement



Severability



Waiver



Relationship



Amendments



Notices



Survival



Counterparts Payment terms Who Pays



How Much



When



Mode



Taxes



Invoice Cycle



TDS



Penalty



Discount



ReimbursementAddress



Email



Phone



Contact Person



Department



Notice AddressSigned By



Designation



Signature Present



Seal Present



Witness



Digital Signature



Company StampRBI



SEBI



Companies Act



Banking Regulation Act



GST



Income Tax Act



Data Privacy



Applicable LawsPay within 30 days



Review services



Provide instructions

id

agreement_type

licensor_name

licensor_father_name

licensee_name

start_date

end_date

location

monthly_rent

security_deposit

licensor_obligations

licensee_obligations

termination_terms

renewal_terms

governing_law

force_majeure

entire_agreement

arbitration

special_clauses

created_at

updated_at
 
Agreement Fields 
 torch==2.10.0
torchvision==0.25.0
transformers==4.57.1
Pillow==12.1.1
matplotlib==3.10.8
einops==0.8.2
addict==2.4.0
easydict==1.13
pymupdf==1.27.2.2
psutil==7.2.2
azure-ai-contentunderstanding==1.0.0
azure-storage-blob==12.25.1
azure-identity==1.23.0import sys
import json
import base64
import time
import requests
import os

# Load environment variables from .env
def _load_env():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(base_dir, ".env")
    if not os.path.exists(env_path):
        env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    os.environ[k] = v

_load_env()

API_KEY = os.getenv("API_KEY")
ENDPOINT = os.getenv("ENDPOINT")

ANALYZE_URL = (
    f"{ENDPOINT}/documentintelligence/documentModels/prebuilt-contract:analyze"
    f"?api-version=2024-11-30&stringIndexType=utf16CodeUnit&outputContentFormat=markdown"
)

HEADERS = {
    "Ocp-Apim-Subscription-Key": API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}



def analyze_pdf(pdf_path: str) -> dict:
    """
    Run Document Intelligence on a local PDF using prebuilt-contract.
    Returns the raw result as a dict.
    """
    with open(pdf_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    payload = {"base64Source": encoded}

    # Submit with retries
    response = None
    for attempt in range(1, 5):
        try:
            response = requests.post(ANALYZE_URL, headers=HEADERS, json=payload, timeout=120)
        except requests.RequestException as err:
            if attempt < 4:
                time.sleep(2 * attempt)
                continue
            raise RuntimeError(f"POST request failed: {err}") from err

        if response.status_code == 202:
            break
        if response.status_code in (408, 429, 500, 502, 503, 504) and attempt < 4:
            time.sleep(2 * attempt)
            continue
        break

    if response is None or response.status_code != 202:
        status = response.status_code if response is not None else "N/A"
        body   = response.text      if response is not None else "No response"
        raise RuntimeError(f"ADI Error: HTTP {status} — {body}")

    operation_location = response.headers.get("Operation-Location")
    if not operation_location:
        raise RuntimeError("ADI Error: Missing Operation-Location header.")

    # Poll until complete
    while True:
        try:
            poll = requests.get(
                operation_location,
                headers={"Ocp-Apim-Subscription-Key": API_KEY},
                timeout=120,
            )
        except requests.RequestException:
            time.sleep(3)
            continue

        if poll.status_code in (408, 429, 500, 502, 503, 504):
            time.sleep(3)
            continue

        try:
            result = poll.json()
        except ValueError:
            time.sleep(3)
            continue

        status = result.get("status")
        if status == "succeeded":
            return result
        if status == "failed":
            raise RuntimeError(f"ADI Error: {json.dumps(result, indent=2)}")

        time.sleep(2)


# ── Standalone usage ──────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python ADI.py <path_to_pdf>")
        sys.exit(1)

    result = analyze_pdf(sys.argv[1])

    result_str = json.dumps(result, indent=2)
    lines = result_str.splitlines()
    print("=" * 50)
    if len(lines) > 50:
        print("\n".join(lines[:50]))
        print(f"\n  ... {len(lines) - 50} more lines ...")
    else:
        print(result_str)


if __name__ == "__main__":
    main()"""
invoice_extractor.py
═════════════════════════════════════════════════════════════════════
ADI + Invoice Extraction — complete single-file implementation.

Layout (search the banners to jump around):
  1. Logger              - one-line status printer, no debug dumps
  2. Rule Master          - FIELD_RULES table drives extraction (no if/elif chains)
  3. FieldCleaner         - one method per clean_type
  4. Validators           - GSTIN / PAN / IFSC format + OCR-fix logic
  5. Parsing Helpers      - markdown/table/date/paragraph readers shared by extractors
  6. ADIClient            - talks to Azure Document Intelligence only
  7. Extractors           - one class per concern, same extract() contract
  8. PostProcessor        - cross-field fixups that need the full record (flags, PAN
                             derivation, numeric coercion, special cases)
  9. DatabaseManager      - all SQL lives here only
 10. InvoiceProcessor     - orchestrates the pipeline for one PDF
 11. main()               - CLI entry point
═════════════════════════════════════════════════════════════════════
"""

import argparse
import base64
import json
import os
import re
import sys
import time
import shutil
import traceback
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO

import pandas as pd
import pyodbc
import requests
from bs4 import BeautifulSoup

# Use pypdf (modern replacement for PyPDF2)
try:
    from pypdf import PdfReader, PdfWriter
    PDF_LIBRARY_AVAILABLE = True
except ImportError:
    # Fallback to PyPDF2 if pypdf not available
    try:
        from PyPDF2 import PdfReader, PdfWriter
        PDF_LIBRARY_AVAILABLE = True
    except ImportError:
        PDF_LIBRARY_AVAILABLE = False
        PdfReader = None
        PdfWriter = None


# ═══════════════════════════════════════════════════════════════════
# ERROR LOGGER — Centralized error logging to dated folders
# ═══════════════════════════════════════════════════════════════════
class ErrorLogger:
    """Logs errors to Logs/DD-MM-YYYY/scriptname.txt"""

    @staticmethod
    def log_error(script_name: str, error_message: str, exception: Exception = None, logs_folder: str = None):
        """
        Save error to Logs/DD-MM-YYYY/scriptname.txt
        First line will be "ERROR" in caps

        Args:
            script_name: Name of the script (used for log filename)
            error_message: Error message to log
            exception: Optional exception object
            logs_folder: Base logs folder path (defaults to current directory/Logs)
        """
        try:
            # Default logs folder if not provided
            if not logs_folder:
                logs_folder = os.path.join(os.getcwd(), "Logs")

            # Create dated folder
            today_folder = datetime.now().strftime("%d-%m-%Y")
            log_folder = os.path.join(logs_folder, today_folder)
            os.makedirs(log_folder, exist_ok=True)

            # Create log file
            log_file = os.path.join(log_folder, f"{script_name}.txt")

            with open(log_file, "w", encoding="utf-8") as f:
                # Line 1: ERROR
                f.write("ERROR\n")
                # Line 2: Error Message:
                f.write("Error Message:\n")
                # Line 3: Actual error message
                f.write(f"{error_message}\n")

            print(f"\nERROR logged to: {log_file}")

        except Exception as log_err:
            print(f"Failed to write error log: {log_err}")


# ═══════════════════════════════════════════════════════════════════
# 1. LOGGER
# ═══════════════════════════════════════════════════════════════════
class Logger:
    """One line per event. Swap for logging module later if needed."""

    def __init__(self, name: str):
        self.name = name

    def info(self, msg: str):
        print(f"[{self.name}] {msg}")

    def ok(self, msg: str):
        print(f"[{self.name}] OK: {msg}")

    def warn(self, msg: str):
        print(f"[{self.name}] WARNING: {msg}")

    def error(self, msg: str):
        print(f"[{self.name}] ERROR: {msg}")


# ═══════════════════════════════════════════════════════════════════
# 0. PDF UTILITIES — splitting multi-page PDFs (in-memory)
# ═══════════════════════════════════════════════════════════════════
class PDFSplitter:
    """Split multi-page PDF into pages for processing (in-memory, no temp files)"""

    @staticmethod
    def get_page_count(pdf_path: str) -> int:
        """Get number of pages in PDF"""
        if not PDF_LIBRARY_AVAILABLE:
            return 1  # Assume single page if PDF library not available

        try:
            reader = PdfReader(pdf_path)
            return len(reader.pages)
        except Exception:
            return 1

    @staticmethod
    def extract_page_as_bytes(pdf_path: str, page_num: int) -> bytes:
        """Extract a single page from PDF and return as bytes (in-memory).

        Args:
            pdf_path: Path to source PDF
            page_num: Page number (0-indexed)

        Returns:
            PDF bytes for the single page
        """
        if not PDF_LIBRARY_AVAILABLE:
            Logger("PDFSplitter").warn("PDF library not available - cannot split pages")
            return None

        try:
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            writer.add_page(reader.pages[page_num])

            # Write to bytes buffer instead of file
            from io import BytesIO
            buffer = BytesIO()
            writer.write(buffer)
            buffer.seek(0)
            return buffer.getvalue()

        except Exception as e:
            Logger("PDFSplitter").warn(f"page extraction failed: {e}")
            return None


# ═══════════════════════════════════════════════════════════════════
# FILE MANAGER — move processed files to dated output folder
# ═══════════════════════════════════════════════════════════════════
class FileManager:
    """Manages file operations - moving processed PDFs to output folders"""

    @staticmethod
    def rename_pdf_with_invoice_no(pdf_path: str, invoice_no: str, log=None) -> str:
        """Rename PDF file with InvoiceNo.pdf format.

        If a file with the same name already exists, adds random 3-char suffix: InvoiceNo_XXX.pdf

        Args:
            pdf_path: Original PDF file path
            invoice_no: Extracted Invoice_No value
            log: Optional Logger instance

        Returns:
            New PDF file path (or original if rename failed)
        """
        if log is None:
            log = Logger("FileManager")

        if not invoice_no:
            log.warn("Invoice_No is empty - skipping rename")
            return pdf_path

        try:
            import random
            import string

            # Clean invoice_no to make it filesystem-safe
            # Replace problematic characters with underscore
            safe_invoice_no = re.sub(r'[<>:"/\\|?*]', '_', str(invoice_no))
            safe_invoice_no = re.sub(r'\s+', '_', safe_invoice_no)  # Replace spaces with underscore

            # Build new filename: InvoiceNo.pdf
            directory = os.path.dirname(pdf_path)
            new_filename = f"{safe_invoice_no}.pdf"
            new_path = os.path.join(directory, new_filename)

            # If file already exists, add random 3-char suffix
            if os.path.exists(new_path) and new_path != pdf_path:
                random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
                new_filename = f"{safe_invoice_no}_{random_suffix}.pdf"
                new_path = os.path.join(directory, new_filename)

                # Keep trying with different random suffixes if collision occurs (very unlikely)
                counter = 0
                while os.path.exists(new_path) and counter < 100:
                    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
                    new_filename = f"{safe_invoice_no}_{random_suffix}.pdf"
                    new_path = os.path.join(directory, new_filename)
                    counter += 1

                if counter >= 100:
                    log.warn("Could not generate unique filename after 100 attempts")
                    return pdf_path

            # Rename the file
            os.rename(pdf_path, new_path)
            log.ok(f"renamed: {os.path.basename(pdf_path)} → {new_filename}")
            return new_path

        except Exception as e:
            log.warn(f"rename failed: {e}")
            return pdf_path

    @staticmethod
    def move_to_output(pdf_path: str, output_folder: str, log=None):
        """Move processed PDF directly into output folder.

        No dated subfolder is created.
        """
        if not output_folder:
            return

        if log is None:
            log = Logger("FileManager")

        try:
            # Create output folder directly
            os.makedirs(output_folder, exist_ok=True)

            # Move file directly into output folder
            filename = os.path.basename(pdf_path)
            target_path = os.path.join(output_folder, filename)

            # Handle duplicate filenames
            if os.path.exists(target_path):
                base, ext = os.path.splitext(filename)
                counter = 1

                while os.path.exists(target_path):
                    target_path = os.path.join(
                        output_folder,
                        f"{base}_{counter}{ext}"
                    )
                    counter += 1

            shutil.move(pdf_path, target_path)

            log.ok(f"moved to {output_folder}")

        except Exception as e:
            log.warn(f"could not move file: {e}")


# ═══════════════════════════════════════════════════════════════════
# 2. RULE MASTER — the sheet: source field → target field → clean type
# ═══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class FieldRule:
    source: str                # key inside ADI documents[0].fields
    target: str                # key inside invoice_data
    clean_type: str = "text"   # matches a FieldCleaner method name
    required: bool = False


# To add / remove / rename a field, edit only this table.
FIELD_RULES: list[FieldRule] = [
    FieldRule("BillingAddress",           "Company_Address",         "address"),
    FieldRule("BillingAddressRecipient",  "Company_Name",             "text"),
    FieldRule("CustomerName",             "Company_Name_1",           "text"),
    FieldRule("CustomerTaxId",            "Company_GSTIN",            "gstin"),
    FieldRule("InvoiceDate",              "Invoice_Date",             "date"),
    FieldRule("InvoiceId",                "Invoice_No",               "text", required=True),
    FieldRule("InvoiceTotal",             "Total_Payable",            "numeric"),
    FieldRule("ShippingAddress",          "Company_Address_1",        "address"),
    FieldRule("ShippingAddressRecipient", "Company_Address_2",        "text"),
    FieldRule("SubTotal",                 "Amount_Before_GST",        "numeric"),
    FieldRule("VendorAddress",            "Vendor_Address",           "address"),
    FieldRule("VendorName",               "Vendor_Name",              "text"),
    FieldRule("VendorAddressRecipient",   "Vendor_Name_1",            "text"),
    FieldRule("VendorTaxId",              "Vendor_GSTIN",             "gstin"),
    FieldRule("CustomerAddress",          "Company_Address_3",        "address"),
    FieldRule("TotalAmount",              "TotalAmount",              "numeric"),
    FieldRule("AmountDue",                "AmountDue",                "numeric"),
    FieldRule("BalanceForward",           "BalanceForward",           "numeric"),
    FieldRule("CountryRegion",            "CountryRegion",            "text"),
    FieldRule("CustomerId",               "CustomerId",               "text"),
    FieldRule("DueDate",                  "DueDate",                  "date"),
    FieldRule("PONumber",                 "PONumber",                 "text"),
    FieldRule("RemittanceAddress",        "RemittanceAddress",        "address"),
    FieldRule("RemittanceAddressRecipient", "Vendor_Name_2",          "text"),
    FieldRule("ServiceAddress",           "ServiceAddress",           "address"),
    FieldRule("ServiceAddressRecipient",  "ServiceAddressRecipient",  "text"),
    FieldRule("SubtotalAmount",           "Amount_Before_GST_1",      "numeric"),
    FieldRule("TotalDiscountAmount",      "TotalDiscountAmount",      "numeric"),
    FieldRule("TotalTaxAmount",           "TotalTaxAmount",           "numeric"),
    FieldRule("IRN",                      "IRN",                      "text"),
    FieldRule("bank_account_no",          "Bank_Account_No",          "bank_account"),
    FieldRule("bank_branch",              "Bank_Branch",              "text"),
    FieldRule("bank_name",                "Bank_Name",                "text"),
    FieldRule("ifsc_code",                "Bank_IFSC_Code",           "ifsc"),
    FieldRule("vendor_pan_no",            "Vendor_PAN_No",            "pan"),
]

# Fields that exist purely for internal logic (beneficiary resolution) — read
# the same way as FIELD_RULES sources but never written straight into invoice_data.
RAW_ONLY_FIELDS = ["Beneficiary_name", "payble_to"]

# Extra columns invoice_data carries that aren't 1:1 ADI fields — derived,
# computed, or fixed metadata.
_DERIVED_COLUMNS = {
    "Commission_Month": None,
    "IGST": 0.0,
    "CGST": 0.0,
    "SGST": 0.0,
    "Total_Tax": None,
    "Company_PAN_No": None,
    "Total_Amount_In_Words": None,
    "Bank_Payable_To": None,
    "E_way_bill_No": None,
    "E_way_bill_No_Flag": False,
    "IRN_Flag": "False",
    "E_Invoice_Flag": "False",
    "Digital_Signature_Val": False,
    "File_Name": None,
    "Invoice_Type": None,
    "Insertion_Date": None,
    "Place_Of_Supply": None,
    "LOAN_TYPE": None,
}


def blank_invoice_record() -> dict:
    """Single source of truth for 'what columns does an invoice have'."""
    record = {rule.target: None for rule in FIELD_RULES}
    record.update(_DERIVED_COLUMNS)
    return record


# ═══════════════════════════════════════════════════════════════════
# 3. FIELD CLEANER — one method per clean_type
# ═══════════════════════════════════════════════════════════════════
class FieldCleaner:

    @staticmethod
    def clean(value, clean_type: str = "text"):
        if value is None or value == "":
            return None
        value = re.sub(r"\s+", " ", str(value).strip())
        value = re.sub(r'["“”‘’`´]', "", value)     # smart quotes
        value = re.sub(r"[•●○◦▪▫]", "", value)       # bullets
        method = getattr(FieldCleaner, clean_type, FieldCleaner.text)
        cleaned = method(value)
        return cleaned.strip() if isinstance(cleaned, str) and cleaned.strip() else cleaned or None

    @staticmethod
    def text(value: str) -> str:
        value = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", value)          # control chars
        value = re.sub(r"([!?.,;:]){2,}", r"\1", value)               # repeated punctuation
        return value

    @staticmethod
    def numeric(value: str) -> str:
        value = re.sub(r"[^\d.\-]", "", value)
        parts = value.split(".")
        if len(parts) > 2:
            value = parts[0] + "." + "".join(parts[1:])
        return value

    @staticmethod
    def address(value: str) -> str:
        value = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value

    @staticmethod
    def date(value: str) -> str:
        return re.sub(r"[^\d\-/.\s]", "", value)

    @staticmethod
    def bank_account(value: str) -> str:
        value = re.sub(r"[^\d\-\s]", "", value)
        return re.sub(r"\s+", "", value)

    @staticmethod
    def gstin(value: str):
        return GSTINValidator.clean(value)

    @staticmethod
    def pan(value: str):
        return PANValidator.clean(value)

    @staticmethod
    def ifsc(value: str):
        return IFSCValidator.clean(value)


# ═══════════════════════════════════════════════════════════════════
# 4. VALIDATORS — GSTIN / PAN / IFSC format checks + OCR-typo fixes
# ═══════════════════════════════════════════════════════════════════
GSTIN_PATTERN = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z][A-Z0-9]")
PAN_PATTERN = re.compile(r"[A-Z]{5}\d{4}[A-Z]")
IFSC_PATTERN = re.compile(r"[A-Z]{4}0[A-Z0-9]{6}")

# GSTIN position rules: D=must be digit, L=must be letter, Z=always literal 'Z', X=leave alone (checksum)
_GSTIN_POSITION_RULES = list("DDLLLLLDDDDLDZX")
_LETTER_TO_DIGIT = {"O": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "G": "6", "D": "0", "Q": "0", "T": "7"}
_DIGIT_TO_LETTER = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B", "6": "G", "7": "T"}

_KNOWN_IFSC_BANK_CODES = {
    "ICIC", "HDFC", "SBIN", "UTIB", "KKBK", "YESB", "IDIB", "PUNB", "BARB", "BKID",
    "CNRB", "UBIN", "IOBA", "CBIN", "SYNB", "ALLA", "ANDB", "CITI", "SCBL", "HSBC",
    "DEUT", "KARB", "MAHB", "FDRL", "TMBL", "RATN", "INDB", "VIJB", "PYTM", "AIRP",
    "IDFB", "UNBA",
}


class GSTINValidator:
    @staticmethod
    def clean(value: str):
        value = re.sub(r"(?i)^(gstin|gst)\s*(no\.?)?\s*[:\-\s]?\s*", "", value.strip())
        value = re.sub(r"[^A-Z0-9]", "", value.upper())

        if len(value) != 15:
            embedded = GSTIN_PATTERN.search(value)
            return embedded.group(0) if embedded else None

        match = GSTIN_PATTERN.match(value)
        return match.group(0) if match else None

    @staticmethod
    def fix_ocr_typos(gstin: str) -> str:
        """Correct common OCR letter/digit confusion at each fixed GSTIN position."""
        if not gstin or len(gstin) != 15:
            return gstin

        chars = list(gstin)
        for i, rule in enumerate(_GSTIN_POSITION_RULES):
            ch = chars[i]
            if rule == "D" and ch.isalpha():
                chars[i] = _LETTER_TO_DIGIT.get(ch, ch)
            elif rule == "L" and ch.isdigit():
                chars[i] = _DIGIT_TO_LETTER.get(ch, ch)
            elif rule == "Z" and ch != "Z":
                chars[i] = "Z"
            # rule == "X": checksum digit, leave untouched
        return "".join(chars)

    @staticmethod
    def pan_from_gstin(gstin: str):
        """PAN is embedded in GSTIN at positions 2:12."""
        if gstin and len(gstin) == 15:
            candidate = gstin[2:12]
            if PAN_PATTERN.match(candidate):
                return candidate
        return None


class PANValidator:
    @staticmethod
    def clean(value: str):
        value = re.sub(r"[^A-Z0-9]", "", value.upper())
        if len(value) != 10:
            return value  # length check failed — return as-is, caller decides
        match = PAN_PATTERN.match(value)
        return match.group(0) if match else value

    @staticmethod
    def is_valid(value) -> bool:
        """Strict check: exactly 10 chars, full PAN structure
        (5 letters + 4 digits + 1 letter). Used before trusting any value —
        from a mislabeled field, a generic table row, or a raw-content scan —
        as an actual PAN."""
        if not value:
            return False
        candidate = re.sub(r"[^A-Z0-9]", "", str(value).upper())
        return len(candidate) == 10 and bool(PAN_PATTERN.fullmatch(candidate))


class IFSCValidator:
    @staticmethod
    def clean(value: str):
        value = re.sub(r"[^A-Z0-9]", "", value.upper())
        match = IFSC_PATTERN.search(value)
        return match.group(0) if match else value

    @staticmethod
    def is_valid(value) -> bool:
        return bool(value and len(str(value)) == 11 and IFSC_PATTERN.fullmatch(str(value)))

    @staticmethod
    def extract_from_text(content: str):
        """Multi-strategy scan: context keywords -> bank name proximity -> known bank codes."""
        if not content:
            return None

        context_patterns = [
            r"(?:IFSC|IFS|RTGS|NEFT)\s*(?:Code)?\s*[:\-]?\s*([A-Z]{4}0[A-Z0-9]{6})",
            r"([A-Z]{4}0[A-Z0-9]{6})\s*(?:IFSC|IFS|RTGS|NEFT)",
        ]
        for pattern in context_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).upper()

        all_matches = re.findall(r"\b([A-Z]{4}0[A-Z0-9]{6})\b", content.upper())
        for candidate in all_matches:
            if candidate[:4] in _KNOWN_IFSC_BANK_CODES:
                return candidate
        return all_matches[0] if all_matches else None


# ═══════════════════════════════════════════════════════════════════
# 5. PARSING HELPERS — markdown / tables / dates / paragraphs
# ═══════════════════════════════════════════════════════════════════
def get_primary_fields(analyze_result: dict) -> dict:
    return analyze_result.get("analyzeResult", {}).get("documents", [{}])[0].get("fields", {})


def get_raw_field_value(field: dict):
    """Pull the scalar value out of an ADI field dict, whatever its type."""
    if not field:
        return None
    if "valueString" in field:
        return str(field["valueString"])
    if "valueDate" in field:
        return str(field["valueDate"])
    if field.get("type") == "currency" and "valueCurrency" in field:
        amount = field["valueCurrency"].get("amount")
        return str(amount) if amount is not None else None
    if field.get("type") == "address":
        return field.get("content", "")
    if "content" in field:
        return str(field["content"])
    return None


def extract_markdown(analyze_result: dict) -> str:
    result = analyze_result.get("analyzeResult", {})
    content = result.get("content", [])

    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and "markdown" in item:
                return item["markdown"]
    elif isinstance(content, str):
        return content

    markdown = ""
    for page in result.get("pages", []):
        markdown += page.get("markdown", "")
    return markdown


def extract_paragraphs(analyze_result: dict) -> list:
    result = analyze_result.get("analyzeResult", {})
    content = result.get("content", [])
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and "paragraphs" in item:
                return item["paragraphs"]
    return []


def find_date_in_text(text: str):
    """Scan free text for a date in any common format and normalize to YYYY-MM-DD."""
    if not text:
        return None

    date_pattern = r"""
    \b(\d{4}[-/.]\d{2}[-/.]\d{2}|\d{2}[-/.]\d{2}[-/.]\d{4}|\d{2}[-/.]\d{2}[-/.]\d{2}
    |\d{2}\s+(January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{4}
    |\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}
    |(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*\d{4}
    )\b"""

    formats = [
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%Y/%m/%d",
        "%d.%m.%Y", "%Y.%m.%d", "%d %b %Y", "%d %B, %Y", "%d %B %Y",
        "%B %d, %Y", "%B %d,%Y",
    ]
    for match in re.compile(date_pattern, re.VERBOSE).findall(text):
        date_str = match[0] if isinstance(match, tuple) else match
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None


def classify_markdown_tables(markdown: str) -> dict:
    """Split HTML tables inside markdown into bank / gst / invoice-line tables by column signature."""
    result = {"bank": pd.DataFrame(), "gst": pd.DataFrame(), "invoice": pd.DataFrame()}
    if not markdown:
        return result

    soup = BeautifulSoup(markdown, "html.parser")
    for html_table in soup.find_all("table"):
        try:
            df = pd.read_html(StringIO(str(html_table)))[0].replace("", pd.NA)
        except Exception:
            continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [
                " ".join(str(x) for x in col if str(x).lower() not in ("", "nan")).strip()
                for col in df.columns
            ]

        signature = re.sub(
            r"[^a-z]", "",
            (" ".join(df.columns.astype(str)) + " " + " ".join(pd.Series(df.values.flatten()).fillna("").astype(str))).lower(),
        )

        is_bank = all(k in signature for k in ("bank", "account", "ifsc"))
        is_gst = any(k in signature for k in ("cgst", "sgst", "igst"))
        is_invoice = any(k in signature for k in ("disb", "roi", "payout", "region", "pf"))

        if is_bank:
            result["bank"] = df
        elif is_gst and not is_invoice:
            result["gst"] = df
        elif is_invoice and result["invoice"].empty:
            result["invoice"] = df

    return result


def to_float(value, default=None):
    try:
        return round(float(Decimal(str(value).replace(",", "").strip())), 2)
    except (InvalidOperation, TypeError, ValueError):
        return default


# ═══════════════════════════════════════════════════════════════════
# 6. ADI CLIENT — Azure Document Intelligence only, no business logic
# ═══════════════════════════════════════════════════════════════════
class ADIClient:
    RETRYABLE_STATUSES = (408, 429, 500, 502, 503, 504)

    def __init__(self, endpoint: str, api_key: str, log: Logger = None):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.log = log or Logger("ADI")
        self.analyze_url = (
            f"{self.endpoint}/documentintelligence/documentModels/prebuilt-invoice:analyze"
            f"?api-version=2024-11-30&stringIndexType=utf16CodeUnit&queryFields=IRN&features=queryFields"
        )
        self.headers = {
            "Ocp-Apim-Subscription-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def analyze(self, pdf_path: str) -> dict | None:
        """Submit + poll. Returns the parsed result dict, or None on failure."""
        encoded = self._read_pdf_base64(pdf_path)
        if encoded is None:
            return None

        operation_location = self._submit(encoded)
        if not operation_location:
            return None

        return self._poll(operation_location)

    def analyze_bytes(self, pdf_bytes: bytes, page_label: str = "page") -> dict | None:
        """Analyze PDF from bytes (in-memory) instead of file path.

        Args:
            pdf_bytes: PDF content as bytes
            page_label: Label for logging (e.g., "page 1", "page 2")
        """
        try:
            encoded = base64.b64encode(pdf_bytes).decode("utf-8")
            operation_location = self._submit(encoded)
            if not operation_location:
                return None
            return self._poll(operation_location)
        except Exception as e:
            self.log.error(f"analyze_bytes failed for {page_label}: {e}")
            return None

    def _read_pdf_base64(self, pdf_path: str):
        try:
            with open(pdf_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except FileNotFoundError:
            self.log.error(f"file not found: {pdf_path}")
            return None

    def _submit(self, encoded_pdf: str) -> str | None:
        payload = {"base64Source": encoded_pdf}
        response = None

        for attempt in range(1, 5):
            try:
                response = requests.post(self.analyze_url, headers=self.headers, json=payload, timeout=120)
            except requests.RequestException as err:
                self.log.warn(f"submit error (attempt {attempt}/4): {err}")
                time.sleep(2 * attempt)
                continue

            if response.status_code == 202:
                return response.headers.get("Operation-Location")
            if response.status_code in self.RETRYABLE_STATUSES:
                self.log.warn(f"transient status {response.status_code} (attempt {attempt}/4)")
                time.sleep(2 * attempt)
                continue
            break  # non-retryable failure

        status = response.status_code if response is not None else "N/A"
        self.log.error(f"submit failed, status={status}")
        return None

    def _poll(self, operation_location: str) -> dict | None:
        max_wait = 300  # 5 minutes max per document
        elapsed = 0
        while elapsed < max_wait:
            try:
                response = requests.get(
                    operation_location,
                    headers={"Ocp-Apim-Subscription-Key": self.api_key},
                    timeout=120,
                )
            except requests.RequestException as err:
                self.log.warn(f"poll error: {err}")
                time.sleep(3)
                elapsed += 3
                continue

            if response.status_code in self.RETRYABLE_STATUSES:
                time.sleep(3)
                elapsed += 3
                continue

            try:
                result = response.json()
            except ValueError:
                time.sleep(3)
                elapsed += 3
                continue

            status = result.get("status")
            if status == "succeeded":
                return result
            if status == "failed":
                self.log.error("ADI extraction failed")
                return None
            time.sleep(2)
            elapsed += 2

        self.log.error(f"ADI polling timed out after {max_wait}s")
        return None


# ═══════════════════════════════════════════════════════════════════
# 7. EXTRACTORS — one class per concern, same extract() contract
# ═══════════════════════════════════════════════════════════════════
class BaseExtractor:
    name = "extractor"

    def extract(self, analyze_result: dict, invoice_data: dict) -> dict:
        raise NotImplementedError


class PrimaryFieldExtractor(BaseExtractor):
    """Replaces the old giant if/elif block — just walks FIELD_RULES."""
    name = "PrimaryFieldExtractor"

    # When a *TaxId field (meant to hold a GSTIN) fails GSTIN validation, check
    # whether it's actually a bare PAN — common for individual vendors who have
    # no GSTIN at all and whose PAN ends up sitting in the tax-id field instead.
    _TAX_ID_PAN_FALLBACK = {
        "VendorTaxId": "Vendor_PAN_No",
        "CustomerTaxId": "Company_PAN_No",
    }

    def __init__(self, log: Logger = None):
        self.log = log or Logger(self.name)

    def extract(self, analyze_result: dict, invoice_data: dict) -> dict:
        fields = get_primary_fields(analyze_result)
        filled = 0

        for rule in FIELD_RULES:
            raw_value = get_raw_field_value(fields.get(rule.source))
            if raw_value is None:
                if rule.required:
                    self.log.warn(f"required field missing: {rule.source}")
                continue

            cleaned = FieldCleaner.clean(raw_value, rule.clean_type)
            if cleaned:
                invoice_data[rule.target] = cleaned
                filled += 1
            elif rule.clean_type == "gstin":
                # GSTIN clean failed — before giving up, check if the raw value
                # is actually a valid PAN mislabeled under a *TaxId field.
                pan_target = self._TAX_ID_PAN_FALLBACK.get(rule.source)
                if pan_target and not invoice_data.get(pan_target):
                    candidate = re.sub(r"[^A-Z0-9]", "", raw_value.upper())
                    if PANValidator.is_valid(candidate):
                        invoice_data[pan_target] = candidate
                        filled += 1
                        self.log.ok(f"{rule.source}={candidate} looked like a PAN, not GSTIN — routed to {pan_target}")

        self.log.ok(f"{filled}/{len(FIELD_RULES)} fields populated")
        return invoice_data


class DocumentFlagExtractor(BaseExtractor):
    """Cheap presence flags (IRN / Document No / e-Invoice) from the raw content blob."""
    name = "DocumentFlagExtractor"

    def extract(self, analyze_result: dict, invoice_data: dict) -> dict:
        blob = str(analyze_result.get("analyzeResult", {})).lower()
        invoice_data["IRN_Flag"] = str("irn" in blob)
        invoice_data["E_Invoice_Flag"] = str("e-invoice" in blob)
        invoice_data["Digital_Signature_Val"] = any(k in blob for k in ("digitally", "signed"))
        return invoice_data


class CommissionMonthExtractor(BaseExtractor):
    """Finds 'commission/service ... for/of ... the <Month Year>' in paragraphs,
    falls back to a bare '<month><year>' scan across the whole markdown."""
    name = "CommissionMonthExtractor"

    _MONTH_YEAR = re.compile(
        r"\b(JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|JUN(?:E)?|JUL(?:Y)?|"
        r"AUG(?:UST)?|SEP(?:TEMBER)?|OCT(?:OBER)?|NOV(?:EMBER)?|DEC(?:EMBER)?)\s*[-,]?\s*(\d{2,4})\b",
        re.IGNORECASE,
    )
    _MONTHS = [
        "january", "february", "march", "april", "may", "june", "july", "august",
        "september", "october", "november", "december",
        "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    ]

    def extract(self, analyze_result: dict, invoice_data: dict) -> dict:
        paragraphs = extract_paragraphs(analyze_result)

        for idx, para in enumerate(paragraphs):
            content = re.sub(r"[^A-Za-z0-9]", " ", para.get("content", "")).upper()
            if ("SERVICE" in content or "COMMISSION" in content) and ("OF" in content or "FOR" in content) and "THE" in content:
                window = " ".join(p.get("content", "") for p in paragraphs[idx: idx + 5])
                match = self._MONTH_YEAR.search(window)
                if match:
                    invoice_data["Commission_Month"] = FieldCleaner.clean(f"{match.group(1).upper()} {match.group(2)}")
                    self.log_result(invoice_data)
                    return invoice_data

        markdown = extract_markdown(analyze_result)
        fallback = self._scan_month_year(markdown)
        if fallback:
            invoice_data["Commission_Month"] = fallback.upper()

        self.log_result(invoice_data)
        return invoice_data

    def _scan_month_year(self, text: str):
        if not text:
            return None
        clean = re.sub(r"[^a-z0-9]", "", text.lower())
        current_year, prev_year = datetime.today().year, datetime.today().year - 1
        year_parts = [str(current_year), str(current_year)[-2:], str(prev_year), str(prev_year)[-2:]]
        for month in self._MONTHS:
            for year in year_parts:
                if f"{month}{year}" in clean:
                    return f"{month}{year}"
        return None

    def log_result(self, invoice_data):
        Logger(self.name).ok(f"Commission_Month={invoice_data.get('Commission_Month')}")


class GSTExtractor(BaseExtractor):
    """Reads CGST/SGST/IGST from TaxDetails; calculates basic amount from GST% and Total Payable."""
    name = "GSTExtractor"

    _LABELS = {
        "CGST": ("cgst", "csgt", "c gst", "c-gst", "cg st"),
        "SGST": ("sgst", "s gst", "s-gst", "sg st"),
        "IGST": ("igst", "i gst", "i-gst", "ig st"),
    }

    def __init__(self, log: Logger = None):
        self.log = log or Logger(self.name)

    def extract(self, analyze_result: dict, invoice_data: dict) -> dict:
        # Extract GST amounts from TaxDetails first
        self._extract_from_tax_details(analyze_result, invoice_data)

        # Calculate basic amount from actual GST amounts and Total_Payable
        if invoice_data.get("Total_Payable"):
            self._calculate_basic_amount_from_gst(invoice_data)

        # If all GST amounts are still zero, try fallback strategies
        if self._all_zero(invoice_data):
            # Try GST percentage approach
            gst_percentage = self._extract_gst_percentage(analyze_result)
            if gst_percentage and invoice_data.get("Total_Payable"):
                self._calculate_from_gst_percentage(gst_percentage, invoice_data)
            else:
                # Final fallback to state-code split
                self._apply_state_code_fallback(invoice_data)

        self.log.ok(f"CGST={invoice_data['CGST']} SGST={invoice_data['SGST']} IGST={invoice_data['IGST']}")
        return invoice_data

    def _all_zero(self, invoice_data: dict) -> bool:
        return invoice_data["CGST"] == 0.0 and invoice_data["SGST"] == 0.0 and invoice_data["IGST"] == 0.0

    def _extract_gst_percentage(self, analyze_result: dict) -> float:
        """Extract GST percentage (e.g., 18%, 12%, 9%) from TaxDetails."""
        tax_details = get_primary_fields(analyze_result).get("TaxDetails", {}).get("valueArray", [])

        for item in tax_details:
            content = item.get("content", "").strip()
            value_object = item.get("valueObject", {})

            # Check for Rate field (percentage)
            if "Rate" in value_object and "valueNumber" in value_object["Rate"]:
                rate = value_object["Rate"]["valueNumber"]
                if rate and 0 < rate <= 100:
                    self.log.ok(f"found GST percentage: {rate}%")
                    return float(rate)

            # Fallback: scan content for percentage pattern (e.g., "18%", "9.00%")
            percentage_match = re.search(r"(\d+(?:\.\d+)?)\s*%", content)
            if percentage_match:
                rate = float(percentage_match.group(1))
                if 0 < rate <= 100:
                    self.log.ok(f"found GST percentage from content: {rate}%")
                    return rate

        return None

    def _calculate_basic_amount_from_gst(self, invoice_data: dict):
        """Calculate Basic Amount from actual CGST/SGST/IGST amounts and Total Payable."""
        total_payable = to_float(invoice_data.get("Total_Payable"))

        if not total_payable or total_payable <= 0:
            return

        # Get actual GST amounts from ADI extraction
        cgst = to_float(invoice_data.get("CGST"), 0.0)
        sgst = to_float(invoice_data.get("SGST"), 0.0)
        igst = to_float(invoice_data.get("IGST"), 0.0)

        # Calculate total GST = CGST + SGST + IGST
        total_gst = round(cgst + sgst + igst, 2)

        if total_gst > 0 and total_gst < total_payable:
            # Formula: Basic Amount = Total Payable - Total GST
            basic_amount = round(total_payable - total_gst, 2)

            self.log.ok(f"calculated from actual GST amounts: Basic={basic_amount}, Total GST={total_gst}")

            # Update Amount_Before_GST if not already set
            if not invoice_data.get("Amount_Before_GST"):
                invoice_data["Amount_Before_GST"] = basic_amount

    def _calculate_from_gst_percentage(self, gst_percentage: float, invoice_data: dict):
        """Calculate Basic Amount and GST Amount from GST percentage and Total Payable."""
        total_payable = to_float(invoice_data.get("Total_Payable"))

        if not total_payable or total_payable <= 0:
            self.log.warn("Total_Payable not available for GST calculation")
            return

        # Formula: Basic Amount = (100 / (100 + GST%)) × Total Payable
        basic_amount = round((100 / (100 + gst_percentage)) * total_payable, 2)

        # Formula: GST Amount = Total Payable - Basic Amount
        gst_amount = round(total_payable - basic_amount, 2)

        self.log.ok(f"calculated from {gst_percentage}% GST: Basic={basic_amount}, GST={gst_amount}")

        # Update Amount_Before_GST if not already set
        if not invoice_data.get("Amount_Before_GST"):
            invoice_data["Amount_Before_GST"] = basic_amount

        # Distribute GST amount to CGST/SGST or IGST based on state codes
        vendor_state = (invoice_data.get("Vendor_GSTIN") or "")[:2]
        company_state = (invoice_data.get("Company_GSTIN") or "")[:2]

        # If states match → CGST + SGST (split 50/50)
        # If states differ → IGST (full amount)
        if vendor_state.isdigit() and company_state.isdigit() and vendor_state == company_state:
            half = round(gst_amount / 2, 2)
            invoice_data["CGST"] = half
            invoice_data["SGST"] = half
            invoice_data["IGST"] = 0.0
            self.log.ok(f"same state → CGST={half}, SGST={half}")
        else:
            invoice_data["IGST"] = gst_amount
            invoice_data["CGST"] = 0.0
            invoice_data["SGST"] = 0.0
            self.log.ok(f"different state → IGST={gst_amount}")

    def _extract_from_tax_details(self, analyze_result: dict, invoice_data: dict):
        tax_details = get_primary_fields(analyze_result).get("TaxDetails", {}).get("valueArray", [])
        pending_type = None

        for item in tax_details:
            content = item.get("content", "").lower().strip()
            value_object = item.get("valueObject", {})
            amount = None
            if "valueCurrency" in value_object.get("Amount", {}):
                amount = value_object["Amount"]["valueCurrency"].get("amount")

            for tax_type, labels in self._LABELS.items():
                if any(label in content for label in labels):
                    pending_type = tax_type
                    break

            if amount is not None and pending_type and invoice_data[pending_type] == 0.0:
                invoice_data[pending_type] = float(amount)
                pending_type = None

    def _apply_state_code_fallback(self, invoice_data: dict):
        tax_amount = (
            to_float(invoice_data.get("Total_Tax"))
            or to_float(invoice_data.get("TotalTaxAmount"))
        )
        if tax_amount is None:
            total = to_float(invoice_data.get("Total_Payable") or invoice_data.get("TotalAmount"))
            subtotal = to_float(invoice_data.get("Amount_Before_GST"))
            if total and subtotal and total > subtotal:
                tax_amount = total - subtotal

        if not tax_amount:
            self.log.warn("no tax amount available — skipping GST fallback")
            return

        vendor_state = (invoice_data.get("Vendor_GSTIN") or "")[:2]
        company_state = (invoice_data.get("Company_GSTIN") or "")[:2]

        if vendor_state.isdigit() and company_state.isdigit() and vendor_state == company_state:
            half = round(tax_amount / 2, 2)
            invoice_data["CGST"] = half
            invoice_data["SGST"] = half
        else:
            invoice_data["IGST"] = tax_amount


class ItemsExtractor(BaseExtractor):
    """Line items: ADI's structured Items[] first, markdown table as fallback.
    Result lives in self.result_df — line items are a separate table, not invoice_data."""
    name = "ItemsExtractor"

    _COLUMN_ALIASES = {
        "Item_Description": ["item_description", "description", "particulars", "particular", "service", "product"],
        "Region": ["region", "state", "location"],
        "Disbursement_Amount": ["disbursement_amount", "amount", "total_amount", "grand_total", "net_amount"],
        "ROI_Percent": ["roi_percent", "roi", "interest", "rate"],
        "PF_Percent": ["pf_percent", "pf"],
        "Payout_Percent": ["payout_percent", "payout"],
        "Subvention_Percent": ["subvention_percent", "subvention"],
        "HSN_Code": ["hsn_code", "hsn", "sac", "code"],
        "Quantity": ["quantity", "qty"],
        "Unit": ["unit", "uom"],
        "Unit_Amount": ["unit_amount", "unit price", "unitprice", "rate", "price"],
        "Discount_Amount": ["discount_amount", "discount"],
        "Taxable_Amount": ["taxable_amount", "taxable", "amount_before_gst", "assessable_amount"],
        "Total_Amount": ["total_amount", "amount", "line_total", "net_amount"],
        "Total_Payout": ["total_payout", "payout"],
        "Invoice_Type": ["invoice_type", "type"],
    }

    def __init__(self, log: Logger = None):
        self.log = log or Logger(self.name)
        self.result_df: pd.DataFrame = pd.DataFrame()

    def extract(self, analyze_result: dict, invoice_data: dict) -> dict:
        items = get_primary_fields(analyze_result).get("Items", {}).get("valueArray", [])
        if items:
            self.result_df = self._from_items_array(items, invoice_data)
        else:
            tables = classify_markdown_tables(extract_markdown(analyze_result))
            self.result_df = self._from_markdown_table(tables["invoice"], invoice_data)

        self.log.ok(f"{len(self.result_df)} line item(s) extracted")
        return invoice_data

    def _from_items_array(self, items: list, invoice_data: dict) -> pd.DataFrame:
        rows = []
        for sr_no, item in enumerate(items, start=1):
            value_object = item.get("valueObject", {})
            row = {
                "Invoice_No": invoice_data.get("Invoice_No"),
                "Sr_No": sr_no,
                "Item_Description": FieldCleaner.clean(get_raw_field_value(value_object.get("Description", {}))),
                "HSN_Code": get_raw_field_value(value_object.get("ProductCode", {})),
                "Quantity": get_raw_field_value(value_object.get("Quantity", {})),
                "Unit": get_raw_field_value(value_object.get("Unit", {})),
                "Unit_Amount": get_raw_field_value(value_object.get("UnitPrice", {})),
                "Discount_Amount": get_raw_field_value(value_object.get("DiscountAmount", {})),
                "Taxable_Amount": get_raw_field_value(value_object.get("TaxableAmount", {})),
                "Total_Amount": to_float(get_raw_field_value(value_object.get("Amount", {}))),
                "Total_Payout": get_raw_field_value(value_object.get("TotalPayout", {})),
                "Invoice_Type": get_raw_field_value(value_object.get("InvoiceType", {})),
            }
            row.update(self._parse_content_line(item.get("content", "")))
            rows.append(row)
        return pd.DataFrame(rows)

    def _parse_content_line(self, content: str) -> dict:
        """Line items often only carry the extra numeric columns (Region, ROI%, PF%...)
        inside the raw content string rather than as named ADI fields."""
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        parsed = {"Region": None, "ROI_Percent": None, "PF_Percent": None, "Payout_Percent": None, "Subvention_Percent": None}

        currency_vals, percent_vals, plain_vals = [], [], []
        for line in lines:
            if re.fullmatch(r"[\d,]+", line):
                currency_vals.append(line.replace(",", ""))
            elif re.fullmatch(r"\d+(\.\d+)?%", line):
                percent_vals.append(line.rstrip("%"))
            elif re.fullmatch(r"\d+(\.\d+)?", line):
                plain_vals.append(line)
            elif re.fullmatch(r"[A-Za-z .]{2,30}", line) and not re.search(r"PVT|LTD|LIMITED|SERVICES", line, re.I):
                parsed["Region"] = line

        if plain_vals:
            parsed["ROI_Percent"] = float(plain_vals[0])
        if len(percent_vals) == 1:
            parsed["Subvention_Percent"] = float(percent_vals[0])
        elif len(percent_vals) == 2:
            parsed["PF_Percent"], parsed["Subvention_Percent"] = float(percent_vals[0]), float(percent_vals[1])
        elif len(percent_vals) >= 3:
            parsed["PF_Percent"], parsed["Payout_Percent"], parsed["Subvention_Percent"] = (
                float(percent_vals[0]), float(percent_vals[1]), float(percent_vals[2])
            )
        return parsed

    def _from_markdown_table(self, table_df: pd.DataFrame, invoice_data: dict) -> pd.DataFrame:
        if table_df is None or table_df.empty:
            return pd.DataFrame()

        columns_lower = {str(col).strip().lower(): col for col in table_df.columns}

        def pick(row, target_column):
            for alias in self._COLUMN_ALIASES[target_column]:
                source_col = columns_lower.get(alias)
                if source_col is not None and pd.notna(row.get(source_col)):
                    return row.get(source_col)
            return None

        rows = []
        for idx, source_row in table_df.reset_index(drop=True).iterrows():
            row = {"Invoice_No": invoice_data.get("Invoice_No"), "Sr_No": idx + 1}
            for target_column in self._COLUMN_ALIASES:
                value = pick(source_row, target_column)
                is_numeric_col = target_column not in ("Item_Description", "Region", "HSN_Code", "Unit", "Invoice_Type")
                row[target_column] = to_float(value) if is_numeric_col else value
            if any(v is not None for k, v in row.items() if k not in ("Invoice_No", "Sr_No")):
                rows.append(row)
        return pd.DataFrame(rows)


class BankDetailsExtractor(BaseExtractor):
    """Bank Name/Branch/Account/IFSC/Payable-To/PAN, tried in priority order:
    markdown bank table -> vertical Azure 'Banking Details' table -> beneficiary
    resolution -> IFSC text-scan fallback -> PAN text-scan fallback.

    NOTE: The 'Banking Details' block commonly carries a PAN row too
    (Payable to / PAN / Bank Name / Branch / Account No. / IFSC / GST No —
    see sample layout), so PAN is extracted from the SAME sources as the rest
    of the bank fields, not treated as a separate concern."""
    name = "BankDetailsExtractor"

    _BANK_TABLE_ALIASES = {
        "Bank_Name": ["bankname", "bank", "name"],
        "Bank_Branch": ["branch", "bankbranch", "branchname"],
        "Bank_Account_No": ["accountno", "accountnumber", "account", "acno", "a/cno"],
        "Bank_IFSC_Code": ["ifsccode", "ifsc", "ifsccodertgsneft", "rtgs/neft"],
        "Bank_Payable_To": ["payableto", "beneficiary", "beneficiaryname", "accountholder"],
        "Vendor_PAN_No": ["pan", "panno", "pannumber", "pancard", "pancardno"],
    }

    # clean_type to use per target field when writing a value pulled from a
    # generic label:value table (markdown bank table or Azure vertical table)
    _CLEAN_TYPE_BY_TARGET = {
        "Bank_Account_No": "bank_account",
        "Bank_IFSC_Code": "ifsc",
        "Vendor_PAN_No": "pan",
    }

    def __init__(self, log: Logger = None):
        self.log = log or Logger(self.name)

    def extract(self, analyze_result: dict, invoice_data: dict) -> dict:
        markdown = extract_markdown(analyze_result)
        self._from_markdown_bank_table(markdown, invoice_data)
        self._from_azure_banking_details_table(analyze_result.get("analyzeResult", {}).get("tables", []), invoice_data)
        self._resolve_beneficiary_name(analyze_result, invoice_data)

        if not IFSCValidator.is_valid(invoice_data.get("Bank_IFSC_Code")):
            content = analyze_result.get("analyzeResult", {}).get("content", "")
            found = IFSCValidator.extract_from_text(content if isinstance(content, str) else "")
            if found:
                invoice_data["Bank_IFSC_Code"] = found

        # PAN fallback: if no valid PAN has been resolved yet (not from
        # vendor_pan_no field, not from the bank tables above), scan the raw
        # content specifically around the "Banking Details" block, since that's
        # where the PAN row typically sits alongside Payable-to/Bank Name/IFSC.
        if not PANValidator.is_valid(invoice_data.get("Vendor_PAN_No")):
            content = analyze_result.get("analyzeResult", {}).get("content", "")
            found_pan = self._extract_pan_from_content(content if isinstance(content, str) else "")
            if found_pan:
                invoice_data["Vendor_PAN_No"] = found_pan
                self.log.ok(f"Vendor_PAN_No={found_pan} (from Banking Details content scan)")

        self.log.ok(f"Bank_IFSC_Code={invoice_data.get('Bank_IFSC_Code')} Vendor_PAN_No={invoice_data.get('Vendor_PAN_No')}")
        return invoice_data

    # ── internals ──────────────────────────────────────────────────
    def _from_markdown_bank_table(self, markdown: str, invoice_data: dict):
        bank_df = classify_markdown_tables(markdown)["bank"]
        if bank_df.empty:
            return

        columns_lower = {str(col).strip().lower().replace(" ", ""): col for col in bank_df.columns}
        row = bank_df.iloc[0]

        for target, aliases in self._BANK_TABLE_ALIASES.items():
            source_col = next((columns_lower[a] for a in aliases if a in columns_lower), None)
            if source_col is None:
                continue
            value = str(row[source_col]).strip()
            if value and value.lower() not in ("nan", "none", ""):
                clean_type = self._CLEAN_TYPE_BY_TARGET.get(target, "text")
                cleaned = FieldCleaner.clean(value, clean_type)
                # Only trust a PAN pulled from a generic table row if it
                # actually validates — a mis-aligned column shouldn't get written.
                if target == "Vendor_PAN_No" and not PANValidator.is_valid(cleaned):
                    continue
                if cleaned:
                    invoice_data[target] = cleaned

    def _from_azure_banking_details_table(self, tables: list, invoice_data: dict):
        if invoice_data.get("Bank_Name") or not tables:
            return

        label_map = {"payable": "Bank_Payable_To", "beneficiary": "Bank_Payable_To", "bankname": "Bank_Name",
                     "branch": "Bank_Branch", "account": "Bank_Account_No", "ifsc": "Bank_IFSC_Code",
                     "pan": "Vendor_PAN_No"}

        for table in tables:
            table_text = " ".join(cell.get("content", "") for cell in table.get("cells", [])).lower()
            if "bank" not in table_text or ("details" not in table_text and "account" not in table_text):
                continue

            cells = table.get("cells", [])
            for cell in cells:
                label = cell.get("content", "").strip().lower().replace(":", "").replace(" ", "")
                row_idx, col_idx = cell.get("rowIndex", 0), cell.get("columnIndex", 0)
                matched_key = next((key for key in label_map if key in label), None)
                if not matched_key:
                    continue

                value_cell = next((c for c in cells if c.get("rowIndex") == row_idx and c.get("columnIndex") == col_idx + 1), None)
                if not value_cell:
                    continue
                value = value_cell.get("content", "").strip()
                target = label_map[matched_key]
                if value and not invoice_data.get(target):
                    clean_type = self._CLEAN_TYPE_BY_TARGET.get(target, "text")
                    cleaned = FieldCleaner.clean(value, clean_type)
                    # Same guard as above — a "PAN" row that doesn't actually
                    # validate is left alone rather than written as-is.
                    if target == "Vendor_PAN_No" and not PANValidator.is_valid(cleaned):
                        continue
                    if cleaned:
                        invoice_data[target] = cleaned

    def _resolve_beneficiary_name(self, analyze_result: dict, invoice_data: dict):
        fields = get_primary_fields(analyze_result)
        beneficiary = FieldCleaner.clean(get_raw_field_value(fields.get("Beneficiary_name")))
        payable_to = FieldCleaner.clean(get_raw_field_value(fields.get("payble_to")))
        vendor_name = (invoice_data.get("Vendor_Name") or "").strip().upper()

        # Priority 1: explicit Beneficiary_name field (not equal to vendor)
        if beneficiary and beneficiary.strip().upper() != vendor_name:
            invoice_data["Bank_Payable_To"] = beneficiary
            return
        # Priority 2: payble_to custom field
        if payable_to:
            invoice_data["Bank_Payable_To"] = payable_to
            return
        # Priority 3: RemittanceAddressRecipient → Vendor_Name_2 already mapped;
        # also use it for Bank_Payable_To if different from vendor
        vendor_name_2 = (invoice_data.get("Vendor_Name_2") or "").strip()
        if vendor_name_2 and vendor_name_2.upper() != vendor_name:
            invoice_data["Bank_Payable_To"] = vendor_name_2
            return
        # Priority 4: scan raw content for "Payable to : <name>"
        content = analyze_result.get("analyzeResult", {}).get("content", "")
        if isinstance(content, str):
            m = re.search(r"[Pp]ayable\s+to\s*[:\-]\s*([A-Za-z0-9 .&,'\-/]+)", content)
            if m:
                candidate = FieldCleaner.clean(m.group(1).strip())
                if candidate and candidate.upper() != vendor_name:
                    invoice_data["Bank_Payable_To"] = candidate

    @staticmethod
    def _extract_pan_from_content(content: str):
        """PAN commonly sits inside the 'Banking Details' block, in this
        sequence: Payable to -> PAN -> Bank Name -> Branch -> Account No. ->
        IFSC -> GST No. Narrow the scan to that block (when present) so an
        unrelated 10-char token elsewhere on the page never gets picked up,
        then validate the candidate against real PAN structure before
        returning it."""
        if not content:
            return None

        # Narrow to the Banking Details section if the document has one.
        section_match = re.search(r"Banking\s+Details.*", content, re.IGNORECASE | re.DOTALL)
        section = section_match.group(0) if section_match else content
        section = section[:1500]  # don't run away into unrelated later text

        # Strategy 1: explicit "PAN" label followed by a PAN-shaped token.
        m = re.search(r"PAN\s*[:\-]?\s*([A-Z]{5}\d{4}[A-Z])", section, re.IGNORECASE)
        if m:
            candidate = m.group(1).upper()
            if PANValidator.is_valid(candidate):
                return candidate

        # Strategy 2: bare PAN-shaped token anywhere within the Banking
        # Details block, in case OCR dropped/garbled the "PAN" label itself.
        for candidate in re.findall(r"\b([A-Z]{5}\d{4}[A-Z])\b", section.upper()):
            if PANValidator.is_valid(candidate):
                return candidate

        return None


# ═══════════════════════════════════════════════════════════════════
# 8. CONTENT EXTRACTOR — fields that only exist in raw content text
# ═══════════════════════════════════════════════════════════════════
class ContentExtractor(BaseExtractor):
    """Extracts fields that ADI doesn't parse as structured fields:
    Place_Of_Supply, LOAN_TYPE, and Annexure-specific Invoice_No."""
    name = "ContentExtractor"

    # Loan product codes found in Annexure Product column
    _LOAN_TYPES = {"BL", "SC", "LAP", "HL", "GL", "PL", "AL", "TL", "WC", "CC", "OD"}

    def __init__(self, log: Logger = None):
        self.log = log or Logger(self.name)

    def extract(self, analyze_result: dict, invoice_data: dict) -> dict:
        content = analyze_result.get("analyzeResult", {}).get("content", "")
        if not isinstance(content, str):
            return invoice_data

        self._extract_place_of_supply(content, invoice_data)
        self._extract_loan_type(content, analyze_result, invoice_data)
        self._extract_annexure_invoice_no(content, invoice_data)
        self._extract_content_fallbacks(content, invoice_data)
        return invoice_data

    def _extract_place_of_supply(self, content: str, invoice_data: dict):
        if invoice_data.get("Place_Of_Supply"):
            return
        # Pattern 1: "Place of Supply : Delhi"  (E-Invoice format)
        m = re.search(r"Place\s+of\s+Supply\s*[:\-]\s*([A-Za-z][A-Za-z ]{1,30}?)(?:\n|$)", content, re.IGNORECASE)
        if m:
            val = FieldCleaner.clean(m.group(1).strip())
            if val:
                invoice_data["Place_Of_Supply"] = val
                return
        # Pattern 2: table layout — "Place of\n...\nSupply\n<state_name>" — grab state from GSTIN
        company_gstin = invoice_data.get("Company_GSTIN") or ""
        if len(company_gstin) == 15:
            state_code = company_gstin[:2]
            state_map = {
                "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
                "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana", "07": "Delhi",
                "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
                "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
                "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam",
                "19": "West Bengal", "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh",
                "23": "Madhya Pradesh", "24": "Gujarat", "27": "Maharashtra",
                "28": "Andhra Pradesh", "29": "Karnataka", "30": "Goa",
                "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
                "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh",
                "38": "Ladakh",
            }
            state = state_map.get(state_code)
            if state:
                invoice_data["Place_Of_Supply"] = state
        self.log.ok(f"Place_Of_Supply={invoice_data.get('Place_Of_Supply')}")

    def _extract_loan_type(self, content: str, analyze_result: dict, invoice_data: dict):
        if invoice_data.get("LOAN_TYPE"):
            return

        # Strategy 1: Look in Annexure table's Product column via ADI items
        items = get_primary_fields(analyze_result).get("Items", {}).get("valueArray", [])
        for item in items:
            vo = item.get("valueObject", {})
            product_code = get_raw_field_value(vo.get("ProductCode", {}))
            if product_code and product_code.strip().upper() in self._LOAN_TYPES:
                invoice_data["LOAN_TYPE"] = product_code.strip().upper()
                self.log.ok(f"LOAN_TYPE={invoice_data['LOAN_TYPE']} (from Items.ProductCode)")
                return

        # Strategy 2: Regex on raw content — standalone loan code after whitespace/newline
        # e.g. "BL\n3.50" or "\tBL\t" in Annexure content
        for loan_type in self._LOAN_TYPES:
            # Must appear as a standalone word/token between whitespace
            if re.search(rf"(?<!\w){re.escape(loan_type)}(?!\w)", content):
                # Make sure it's in a context that looks like Annexure (has "Product" or "Disbursal")
                if re.search(r"(?i)(product|disbursal|annexure|payout)", content):
                    invoice_data["LOAN_TYPE"] = loan_type
                    self.log.ok(f"LOAN_TYPE={loan_type} (from content regex)")
                    return

        # Strategy 3: Invoice ID pattern — e.g. "ACP/2627/BL/733", "626/BL/DL/0728"
        invoice_no = invoice_data.get("Invoice_No") or ""
        m = re.search(r"/(" + "|".join(self._LOAN_TYPES) + r")/", invoice_no, re.IGNORECASE)
        if m:
            invoice_data["LOAN_TYPE"] = m.group(1).upper()
            self.log.ok(f"LOAN_TYPE={invoice_data['LOAN_TYPE']} (from Invoice_No)")

    def _extract_annexure_invoice_no(self, content: str, invoice_data: dict):
        """For Annexure PDFs: ADI doesn't extract InvoiceId — grab Sales Invoice No from content."""
        if invoice_data.get("Invoice_No"):
            return
        # Annexure content starts with "Annexure\nSales Invoice No\n..."
        # The invoice no appears as the first token that looks like a sales ref
        # Pattern: state_code/year/seq e.g. "DL/2627/000851", "GJ/2627/001208"
        m = re.search(r"\b([A-Z]{2}/\d{4}/\d{4,})\b", content)
        if m:
            invoice_data["Invoice_No"] = m.group(1)
            self.log.ok(f"Invoice_No (Annexure)={invoice_data['Invoice_No']}")
            return
        # Broader fallback: any slash-separated ref after "Sales Invoice No"
        m = re.search(r"Sales\s+Invoice\s+No\s*\n([A-Z0-9/\-]+)", content, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if val:
                invoice_data["Invoice_No"] = val
                self.log.ok(f"Invoice_No (Annexure fallback)={invoice_data['Invoice_No']}")

    def _extract_content_fallbacks(self, content: str, invoice_data: dict):
        """Scan raw content for fields that ADI sometimes misses on non-standard invoices."""

        # Due Date — "Due Date : 10-Aug-2026" / "Payment Due :" / "Due By :" / "Last Date :"
        if not invoice_data.get("DueDate"):
            m = re.search(
                r"(?:Due\s+Date|Payment\s+Due|Due\s+By|Last\s+(?:Date|Payment)\s+Date?)\s*[:\-]\s*"
                r"(\d{1,2}[-/.]\w+[-/.]\d{2,4}|\d{4}[-/.]\d{2}[-/.]\d{2}|\d{1,2}\s+\w+\s+\d{4})",
                content, re.IGNORECASE,
            )
            if m:
                raw = FieldCleaner.clean(m.group(1).strip(), "date")
                invoice_data["DueDate"] = find_date_in_text(raw) or raw

        # Amount Due — "Amount Due : 1,23,456.00" / "Balance Due :" / "Net Payable :" / "Total Due :"
        if not invoice_data.get("AmountDue"):
            m = re.search(
                r"(?:Amount\s+Due|Balance\s+Due|Net\s+Payable|Total\s+Due|Total\s+Payable\s+Amount)\s*[:\-]?\s*"
                r"(?:Rs\.?|INR)?\s*([\d,]+(?:\.\d{1,2})?)",
                content, re.IGNORECASE,
            )
            if m:
                val = to_float(m.group(1).replace(",", ""))
                if val is not None:
                    invoice_data["AmountDue"] = val

        # PO Number — "PO No : ABC123" or "Purchase Order : ..."
        if not invoice_data.get("PONumber"):
            m = re.search(
                r"(?:PO\s*No\.?|Purchase\s+Order\s*(?:No\.?)?|P\.O\.\s*No\.?)\s*[:\-]\s*([A-Z0-9\-/]{3,30})",
                content, re.IGNORECASE,
            )
            if m:
                invoice_data["PONumber"] = FieldCleaner.clean(m.group(1).strip())

        # Customer ID / Reference — "Customer ID : CUST123" or "Ref. No :"
        if not invoice_data.get("CustomerId"):
            m = re.search(
                r"(?:Customer\s*(?:ID|No\.?|Code)|Client\s*(?:ID|Code))\s*[:\-]\s*([A-Z0-9\-/]{3,30})",
                content, re.IGNORECASE,
            )
            if m:
                invoice_data["CustomerId"] = FieldCleaner.clean(m.group(1).strip())

        # Total Amount in Words — "... Only." or "Rupees ... Only"
        if not invoice_data.get("Total_Amount_In_Words"):
            m = re.search(
                r"(?:Rupees\s+)?([A-Z][A-Za-z ,]+(?:Hundred|Thousand|Lakh|Crore|Only)[A-Za-z ,]*\.?)",
                content,
            )
            if m:
                val = FieldCleaner.clean(m.group(0).strip())
                if val and len(val) > 5:
                    invoice_data["Total_Amount_In_Words"] = val


# ═══════════════════════════════════════════════════════════════════
# 9. POST PROCESSOR — cross-field fixups needing the full record
# ═══════════════════════════════════════════════════════════════════
class PostProcessor:
    """Runs after all extractors: GSTIN OCR fixes, PAN derivation, numeric
    coercion, date normalization, and the Unity-bank special case."""

    def __init__(self, log: Logger = None):
        self.log = log or Logger("PostProcessor")

    def run(self, analyze_result: dict, invoice_data: dict) -> dict:
        self._fix_gstins(invoice_data)
        self._derive_pans(invoice_data)
        self._coerce_numeric_fields(invoice_data)
        self._fix_invoice_date(invoice_data)
        self._apply_unity_bank_special_case(analyze_result, invoice_data)
        return invoice_data

    def _fix_gstins(self, invoice_data: dict):
        for key in ("Vendor_GSTIN", "Company_GSTIN"):
            if invoice_data.get(key):
                invoice_data[key] = GSTINValidator.fix_ocr_typos(invoice_data[key])

    def _derive_pans(self, invoice_data: dict):
        if not invoice_data.get("Vendor_PAN_No"):
            invoice_data["Vendor_PAN_No"] = GSTINValidator.pan_from_gstin(invoice_data.get("Vendor_GSTIN"))
        if not invoice_data.get("Company_PAN_No"):
            invoice_data["Company_PAN_No"] = GSTINValidator.pan_from_gstin(invoice_data.get("Company_GSTIN"))

    # All keys that must be stored as plain 2-dp decimals (no scientific notation)
    _NUMERIC_KEYS = (
        "IGST", "CGST", "SGST",
        "Amount_Before_GST", "Amount_Before_GST_1",
        "Total_Payable", "Total_Tax",
        "TotalAmount", "TotalTaxAmount",
        "AmountDue", "BalanceForward",
        "TotalDiscountAmount",
        "SubTotal",
    )

    def _coerce_numeric_fields(self, invoice_data: dict):
        # Round every numeric field to 2 dp — kills scientific notation
        for key in self._NUMERIC_KEYS:
            if invoice_data.get(key) not in (None, ""):
                invoice_data[key] = to_float(invoice_data[key], default=invoice_data[key])

        # Derive Total_Tax = CGST + SGST + IGST if not already set
        if not invoice_data.get("Total_Tax"):
            cgst = to_float(invoice_data.get("CGST"), 0.0)
            sgst = to_float(invoice_data.get("SGST"), 0.0)
            igst = to_float(invoice_data.get("IGST"), 0.0)
            total_tax = round(cgst + sgst + igst, 2)
            if total_tax > 0:
                invoice_data["Total_Tax"] = total_tax

        # Derive Amount_Before_GST if not present: Total_Payable - (CGST + SGST + IGST)
        if not invoice_data.get("Amount_Before_GST") and not invoice_data.get("Amount_Before_GST_1"):
            total_payable = to_float(invoice_data.get("Total_Payable"))
            cgst = to_float(invoice_data.get("CGST"), 0.0)
            sgst = to_float(invoice_data.get("SGST"), 0.0)
            igst = to_float(invoice_data.get("IGST"), 0.0)

            if total_payable and (cgst > 0 or sgst > 0 or igst > 0):
                # Calculate: Amount_Before_GST = Total_Payable - (CGST + SGST + IGST)
                amount_before_gst = round(total_payable - cgst - sgst - igst, 2)
                if amount_before_gst > 0:
                    invoice_data["Amount_Before_GST"] = amount_before_gst
                    self.log.ok(f"derived Amount_Before_GST={amount_before_gst} from Total_Payable - GST")

        # Derive TotalTaxAmount from Total_Tax if not set
        if not invoice_data.get("TotalTaxAmount") and invoice_data.get("Total_Tax"):
            invoice_data["TotalTaxAmount"] = invoice_data["Total_Tax"]

        # Derive TotalAmount = Amount_Before_GST + Total_Tax if not set
        if not invoice_data.get("TotalAmount"):
            subtotal = to_float(invoice_data.get("Amount_Before_GST"))
            total_tax = to_float(invoice_data.get("Total_Tax"))
            if subtotal and total_tax:
                invoice_data["TotalAmount"] = round(subtotal + total_tax, 2)
            elif invoice_data.get("Total_Payable"):
                # Fallback: TotalAmount = Total_Payable
                invoice_data["TotalAmount"] = to_float(invoice_data["Total_Payable"])

    def _fix_invoice_date(self, invoice_data: dict):
        for key in ("Invoice_Date", "DueDate"):
            raw_date = invoice_data.get(key)
            if not raw_date:
                continue
            try:
                datetime.strptime(str(raw_date), "%Y-%m-%d")
            except ValueError:
                fixed = find_date_in_text(str(raw_date))
                if fixed:
                    invoice_data[key] = fixed

    def _apply_unity_bank_special_case(self, analyze_result: dict, invoice_data: dict):
        blob = str(analyze_result.get("analyzeResult", {})).lower()
        if "unity" in blob and "bank" in blob and invoice_data.get("Company_Name") != "Unity Small Finance bank limited":
            invoice_data["Company_Name"] = "Unity Small Finance bank limited"


# ═══════════════════════════════════════════════════════════════════
# 9. DATABASE MANAGER — all SQL lives here only
# ═══════════════════════════════════════════════════════════════════
class DatabaseManager:
    def __init__(self, connection_string: str = None, log: Logger = None):
        self.connection_string = connection_string
        self.log = log or Logger("DB")
        self.cnxn = None
        self.cursor = None
        if connection_string:
            self._connect()

    def _connect(self):
        try:
            self.cnxn = pyodbc.connect(self.connection_string)
            self.cursor = self.cnxn.cursor()
            self.log.ok("connected")
        except Exception as e:
            self.log.warn(f"connection failed, continuing without DB: {e}")

    @property
    def is_connected(self) -> bool:
        return self.cursor is not None

    def _table_columns(self, table: str) -> set:
        self.cursor.execute(f"SELECT TOP 0 * FROM {table}")
        return {desc[0] for desc in self.cursor.description}

    @staticmethod
    def _sanitize(value):
        """Convert Python floats to Decimal so pyodbc never emits scientific notation."""
        if isinstance(value, float):
            return Decimal(f"{value:.2f}")
        return value

    @staticmethod
    def _clean_row(row: dict) -> dict:
        return {k: DatabaseManager._sanitize(v) for k, v in row.items()}

    @staticmethod
    def _clean_tuple(values: tuple) -> tuple:
        return tuple(DatabaseManager._sanitize(v) for v in values)

    def insert_scraping_row(self, table: str, invoice_data: dict):
        """Insert row into scraping table. Returns True if successful, False otherwise."""
        try:
            db_columns = self._table_columns(table)
            row = self._clean_row({k: v for k, v in invoice_data.items() if k in db_columns and v not in ("", None)})
            if not row:
                self.log.warn(f"no matching columns for '{table}'")
                return False
            columns = ", ".join(row.keys())
            placeholders = ", ".join(["?"] * len(row))
            self.cursor.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(row.values()))
            self.cnxn.commit()
            self.log.ok(f"inserted into '{table}'")
            return True
        except Exception as e:
            self.log.error(f"insert into '{table}' failed: {e}")
            return False

    def update_all_fields(self, table: str, invoice_no: str, invoice_data: dict):
        """UPDATE every non-null field for an already-inserted row (used after DSA fallback).
        Returns True if successful, False otherwise."""
        try:
            db_columns = self._table_columns(table)
            row = self._clean_row({k: v for k, v in invoice_data.items()
                   if k in db_columns and k != "Invoice_No" and v not in ("", None)})
            if not row:
                self.log.warn(f"nothing to update for Invoice_No={invoice_no}")
                return True  # Nothing to update is not a failure
            set_clause = ", ".join(f"{k} = ?" for k in row)
            values = tuple(row.values()) + (invoice_no,)
            self.cursor.execute(f"UPDATE {table} SET {set_clause} WHERE Invoice_No = ?", values)
            self.cnxn.commit()
            self.log.ok(f"full row updated for Invoice_No={invoice_no}")
            return True
        except Exception as e:
            self.log.error(f"update for Invoice_No={invoice_no} failed: {e}")
            return False

    def insert_detail_rows(self, table: str, items_df: pd.DataFrame):
        """Insert line items into detail table. Returns True if successful, False otherwise."""
        if items_df.empty:
            return True  # No items to insert is not a failure
        try:
            db_columns = self._table_columns(table)
            insert_df = items_df[[c for c in items_df.columns if c in db_columns]]
            if insert_df.empty:
                self.log.warn(f"no matching columns for '{table}'")
                return False
            columns = list(insert_df.columns)
            placeholders = ", ".join(["?"] * len(columns))
            query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
            rows = [
                self._clean_tuple(row)
                for row in insert_df.itertuples(index=False, name=None)
            ]
            self.cursor.executemany(query, rows)
            self.cnxn.commit()
            self.log.ok(f"inserted {len(insert_df)} line item(s) into '{table}'")
            return True
        except Exception as e:
            self.log.error(f"insert into '{table}' failed: {e}")
            return False

    def update_bank_details(self, table: str, invoice_no: str, bank_fields: dict):
        try:
            self.cursor.execute(
                f"""UPDATE {table}
                    SET Bank_Name = ?, Bank_Payable_To = ?, Bank_Branch = ?,
                        Bank_Account_No = ?, Bank_IFSC_Code = ?
                    WHERE Invoice_No = ?""",
                (
                    bank_fields.get("Bank_Name"), bank_fields.get("Bank_Payable_To"),
                    bank_fields.get("Bank_Branch"), bank_fields.get("Bank_Account_No"),
                    bank_fields.get("Bank_IFSC_Code"), invoice_no,
                ),
            )
            self.cnxn.commit()
            self.log.ok(f"bank details updated for Invoice_No={invoice_no}")
        except Exception as e:
            self.log.error(f"bank details update failed: {e}")

    def close(self):
        if self.cnxn:
            self.cnxn.close()
            self.log.info("connection closed")


# ═══════════════════════════════════════════════════════════════════
# 10. INVOICE PROCESSOR — orchestrates the pipeline for one PDF
# ═══════════════════════════════════════════════════════════════════
class _FloatEncoder(json.JSONEncoder):
    """Serialize floats as fixed-point strings — no scientific notation ever."""
    def iterencode(self, obj, _one_shot=False):
        return super().iterencode(self._fix(obj), _one_shot)

    def _fix(self, obj):
        if isinstance(obj, float):
            return float(f"{obj:.2f}")   # forces Python to repr as plain decimal
        if isinstance(obj, dict):
            return {k: self._fix(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._fix(v) for v in obj]
        return obj


class InvoiceProcessor:
    def __init__(
        self,
        adi_client: ADIClient,
        db: DatabaseManager = None,
        scraping_table: str = None,
        details_table: str = None,
        output_folder: str = None,
        invoice_type: str = None,
        log: Logger = None,
    ):
        self.adi_client = adi_client
        self.db = db
        self.scraping_table = scraping_table
        self.details_table = details_table
        self.output_folder = output_folder
        self.invoice_type = invoice_type
        self.log = log or Logger("Processor")

        # the pipeline — order matters; add/remove/reorder here only
        self.field_extractor = PrimaryFieldExtractor()
        self.flag_extractor = DocumentFlagExtractor()
        self.commission_extractor = CommissionMonthExtractor()
        self.gst_extractor = GSTExtractor()
        self.items_extractor = ItemsExtractor()
        self.bank_extractor = BankDetailsExtractor()
        self.content_extractor = ContentExtractor()
        self.post_processor = PostProcessor()

    def process(self, pdf_path: str, is_temp_page: bool = False, skip_db: bool = False):
        """Process a single PDF or PDF page.

        Args:
            pdf_path: Path to PDF file
            is_temp_page: True if this is a temporary split page (don't move original)
            skip_db: True to skip DB insert (used for multi-page - will insert combined data later)

        Returns:
            tuple: (invoice_data dict, db_success flag, renamed_pdf_path)
        """
        pdf_stem = os.path.splitext(os.path.basename(pdf_path))[0]
        self.log.info(f"processing {pdf_stem}")

        analyze_result = self.adi_client.analyze(pdf_path)
        if analyze_result is None:
            self.log.error(f"ADI failed for {pdf_stem}, skipping")
            return (None, False, pdf_path)

        invoice_data = blank_invoice_record()
        invoice_data["File_Name"] = pdf_stem
        invoice_data["Invoice_Type"] = self.invoice_type
        invoice_data["Insertion_Date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for extractor in (
            self.field_extractor, self.flag_extractor, self.commission_extractor,
            self.gst_extractor, self.bank_extractor, self.content_extractor,
        ):
            invoice_data = extractor.extract(analyze_result, invoice_data)

        self.items_extractor.extract(analyze_result, invoice_data)  # fills .result_df
        invoice_data = self.post_processor.run(analyze_result, invoice_data)

        # Rename PDF file with Invoice_No (only if not a temp page and Invoice_No exists)
        renamed_pdf_path = pdf_path
        if not is_temp_page and invoice_data.get("Invoice_No"):
            renamed_pdf_path = FileManager.rename_pdf_with_invoice_no(pdf_path, invoice_data["Invoice_No"], self.log)
            # Update File_Name in invoice_data to match the new filename (without extension)
            invoice_data["File_Name"] = os.path.splitext(os.path.basename(renamed_pdf_path))[0]

        # Track DB success
        db_success = True

        # Only persist to DB if skip_db=False
        if not skip_db:
            db_success = self._persist(invoice_data, self.items_extractor.result_df)

        if self.output_folder:
            self._save_json({"invoice_data": invoice_data, "analyzeResult": analyze_result.get("analyzeResult")},
                             self.output_folder, invoice_data["File_Name"])

        self.log.ok(f"done: {invoice_data['File_Name']}")
        return (invoice_data, db_success, renamed_pdf_path)

    def process_with_split(self, pdf_path: str):
        """Process PDF - split if multi-page, process each page IN-MEMORY, combine results.
        NO temporary files created - all done in memory.
        Insert to DB only ONCE with combined data from all pages.

        Returns:
            tuple: (list of invoice_data dicts, db_success flag, renamed_pdf_path)
        """
        pdf_stem = os.path.splitext(os.path.basename(pdf_path))[0]

        # Check page count
        page_count = PDFSplitter.get_page_count(pdf_path)
        self.log.info(f"{pdf_stem}: {page_count} page(s)")

        if page_count <= 1:
            # Single page - process normally with DB insert and renaming
            result_tuple = self.process(pdf_path, is_temp_page=False, skip_db=False)
            invoice_data, db_success, renamed_pdf_path = result_tuple if result_tuple else (None, False, pdf_path)
            return ([invoice_data] if invoice_data else [], db_success, renamed_pdf_path)

        # Multi-page - process each page IN-MEMORY (no temp files)
        self.log.info(f"processing {page_count} pages in-memory (no temp files)...")

        results = []
        all_items_dfs = []

        for page_num in range(page_count):
            self.log.info(f"processing page {page_num + 1}/{page_count}...")
            try:
                # Extract page as bytes (in-memory)
                page_bytes = PDFSplitter.extract_page_as_bytes(pdf_path, page_num)
                if not page_bytes:
                    self.log.error(f"page {page_num + 1} extraction failed")
                    continue

                # Analyze page bytes directly (no file)
                page_label = f"{pdf_stem}_page_{page_num + 1}"
                analyze_result = self.adi_client.analyze_bytes(page_bytes, page_label)

                if analyze_result is None:
                    self.log.error(f"ADI failed for page {page_num + 1}")
                    continue

                # Extract data from ADI result
                invoice_data = blank_invoice_record()
                invoice_data["File_Name"] = page_label
                invoice_data["Invoice_Type"] = self.invoice_type
                invoice_data["Insertion_Date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                for extractor in (
                    self.field_extractor, self.flag_extractor, self.commission_extractor,
                    self.gst_extractor, self.bank_extractor, self.content_extractor,
                ):
                    invoice_data = extractor.extract(analyze_result, invoice_data)

                self.items_extractor.extract(analyze_result, invoice_data)
                invoice_data = self.post_processor.run(analyze_result, invoice_data)

                # Save JSON output if needed
                if self.output_folder:
                    self._save_json(
                        {"invoice_data": invoice_data, "analyzeResult": analyze_result.get("analyzeResult")},
                        self.output_folder, page_label
                    )

                results.append(invoice_data)

                # Collect line items
                if not self.items_extractor.result_df.empty:
                    all_items_dfs.append(self.items_extractor.result_df)

                self.log.ok(f"done: page {page_num + 1}")

            except Exception as e:
                self.log.error(f"page {page_num + 1} failed: {e}")

        # Track DB operation success and renamed path
        db_success = False
        renamed_pdf_path = pdf_path

        # Now insert to DB ONCE with combined data
        if results:
            # SMART MERGE: Combine data from all pages - fill gaps from other pages
            primary_invoice_data = self._merge_invoice_data_from_pages(results)

            # Rename PDF file with merged Invoice_No BEFORE DB insert
            if primary_invoice_data.get("Invoice_No"):
                renamed_pdf_path = FileManager.rename_pdf_with_invoice_no(pdf_path, primary_invoice_data["Invoice_No"], self.log)
                # Update File_Name in invoice_data to match the new filename (without extension)
                primary_invoice_data["File_Name"] = os.path.splitext(os.path.basename(renamed_pdf_path))[0]

            # Combine all line items from all pages
            combined_items_df = pd.concat(all_items_dfs, ignore_index=True) if all_items_dfs else pd.DataFrame()

            # Update Invoice_No in all line items to match the merged data
            if not combined_items_df.empty and primary_invoice_data.get("Invoice_No"):
                combined_items_df["Invoice_No"] = primary_invoice_data["Invoice_No"]

            # Insert to DB and track success
            if self.db and self.db.is_connected:
                headers_success = False
                details_success = True  # Default true if no details table configured

                # Insert into Invoice_Headers
                if self.scraping_table:
                    headers_success = self.db.insert_scraping_row(self.scraping_table, primary_invoice_data)

                # Only insert line items if details_table is configured
                if self.details_table and not combined_items_df.empty:
                    details_success = self.db.insert_detail_rows(self.details_table, combined_items_df)
                elif self.details_table and combined_items_df.empty:
                    # Details table configured but no items to insert - treat as success
                    details_success = True

                # Update with final data
                if headers_success:
                    if primary_invoice_data.get("Invoice_No"):
                        update_success = self.db.update_all_fields(self.scraping_table, primary_invoice_data["Invoice_No"], primary_invoice_data)

                        # Overall success: headers inserted + details inserted (if configured) + update successful
                        db_success = headers_success and details_success and update_success

                if db_success:
                    self.log.ok(f"DB insert completed for {primary_invoice_data['File_Name']} ({page_count} pages combined)")
                else:
                    self.log.error(f"DB insert failed for {primary_invoice_data['File_Name']} - file will NOT be moved")

        self.log.ok(f"processed {len(results)}/{page_count} pages for {os.path.basename(renamed_pdf_path)}")
        return (results, db_success, renamed_pdf_path)

    def _check_db_success(self, result_tuple) -> bool:
        """Check if DB operations were successful for single-page processing

        Args:
            result_tuple: (invoice_data, db_success, renamed_pdf_path) tuple from process()
        """
        if result_tuple is None:
            return False

        invoice_data, db_success, renamed_pdf_path = result_tuple
        return db_success and invoice_data is not None

    def _merge_invoice_data_from_pages(self, page_results: list) -> dict:
        """Merge invoice data from multiple pages - fill missing values from any page.

        Strategy:
        1. Start with page 1 as base
        2. For each field, if None/empty/zero in merged, check page 2, 3, etc.
        3. Take the first non-empty value found from any page
        4. For GST amounts (CGST/SGST/IGST), prefer non-zero values
        """
        if not page_results:
            return blank_invoice_record()

        # Start with first page as base
        merged = page_results[0].copy()

        # Track which page contributed each field for logging
        field_sources = {key: 1 for key in merged.keys() if merged.get(key) not in (None, "", 0, 0.0)}

        # For each field, if it's None/empty/zero in merged, try to fill from other pages
        for page_idx, page_data in enumerate(page_results[1:], start=2):
            for key, value in page_data.items():
                current_value = merged.get(key)

                # Check if current value is empty/missing
                is_empty = current_value in (None, "", 0, 0.0, "0", "0.0")

                # Check if new value is meaningful
                is_meaningful = value not in (None, "", 0, 0.0, "0", "0.0")

                # Special handling for GST fields - prefer non-zero values
                if key in ("CGST", "SGST", "IGST", "Total_Tax"):
                    # Replace if current is zero and new is non-zero
                    if is_empty and is_meaningful:
                        merged[key] = value
                        field_sources[key] = page_idx
                        self.log.ok(f"filled {key}={value} from page {page_idx}")
                    # Also replace if new value is larger (more complete extraction)
                    elif is_meaningful and isinstance(value, (int, float)) and isinstance(current_value, (int, float)):
                        if value > current_value:
                            merged[key] = value
                            field_sources[key] = page_idx
                            self.log.ok(f"updated {key}={value} from page {page_idx} (larger value)")

                # For all other fields - fill if empty
                elif is_empty and is_meaningful:
                    merged[key] = value
                    field_sources[key] = page_idx
                    self.log.ok(f"filled {key} from page {page_idx}")

        # Log summary of merge
        pages_used = set(field_sources.values())
        self.log.ok(f"merged data from {len(pages_used)} page(s): {sorted(pages_used)}")

        return merged

    # ── internals ──────────────────────────────────────────────────
    def _persist(self, invoice_data: dict, items_df: pd.DataFrame):
        """Persist data to database. Returns True if all operations successful, False otherwise."""
        if not self.db or not self.db.is_connected:
            self.log.info("no DB — skipping insert")
            return False

        headers_success = False
        details_success = True  # Default true if no details table

        # Insert into Invoice_Headers
        if self.scraping_table:
            headers_success = self.db.insert_scraping_row(self.scraping_table, invoice_data)

        # Only insert line items if details_table is configured
        if self.details_table and not items_df.empty:
            details_success = self.db.insert_detail_rows(self.details_table, items_df)
        elif self.details_table and items_df.empty:
            # Details table configured but no items - not a failure
            details_success = True

        # Always do a full UPDATE after insert so bank details, GST, PAN, etc.
        # that were resolved post-insert are written to the DB.
        if headers_success:
            if invoice_data.get("Invoice_No"):
                update_success = self.db.update_all_fields(self.scraping_table, invoice_data["Invoice_No"], invoice_data)
                return headers_success and details_success and update_success

        return False

    def _save_json(self, data: dict, folder: str, stem: str):
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{stem}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, cls=_FloatEncoder)
        self.log.info(f"saved {path}")


# ═══════════════════════════════════════════════════════════════════
# 11. CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════
def parse_args():
    p = argparse.ArgumentParser(description="ADI + Invoice Extraction")
    p.add_argument("--endpoint", required=True)
    p.add_argument("--api-key", required=True, dest="api_key")
    p.add_argument("--input-folder", required=True, dest="input_folder")
    p.add_argument("--db-connection", default=None, dest="db_connection")
    p.add_argument("--scraping-table", default=None, dest="scraping_table")
    p.add_argument("--details-table", default=None, dest="details_table")
    p.add_argument("--output-folder", default=None, dest="output_folder")
    p.add_argument("--invoice-type", default=None, dest="invoice_type")
    p.add_argument("--logs-folder", default=None, dest="logs_folder", help="Folder for error logs (default: ./Logs)")
    return p.parse_args()


def main():
    """Main function with error logging support"""
    logs_folder = None

    try:
        args = parse_args()
        log = Logger("Main")

        logs_folder = getattr(args, 'logs_folder', None)

        # Warn if PDF library is not available
        if not PDF_LIBRARY_AVAILABLE:
            log.warn("PDF library not installed - multi-page PDFs will be processed as single page")
            log.warn("Install with: pip install pypdf")

        input_folder = os.path.abspath(args.input_folder)
        if not os.path.isdir(input_folder):
            error_msg = f"Input folder not found: {input_folder}"
            log.error(error_msg)
            ErrorLogger.log_error("InvoiceExtraction", error_msg, None, logs_folder)
            sys.exit(1)

        pdf_files = sorted(f for f in os.listdir(input_folder) if f.lower().endswith(".pdf"))
        if not pdf_files:
            log.info("no PDFs found")
            return

        adi_client = ADIClient(args.endpoint, args.api_key)
        db = DatabaseManager(args.db_connection)

        processor = InvoiceProcessor(
            adi_client=adi_client,
            db=db,
            scraping_table=args.scraping_table,
            details_table=args.details_table,
            output_folder=args.output_folder,
            invoice_type=args.invoice_type,
        )

        for pdf_filename in pdf_files:
            pdf_path = os.path.join(input_folder, pdf_filename)
            try:
                # Process PDF with automatic splitting for multi-page PDFs
                results, db_success, renamed_pdf_path = processor.process_with_split(pdf_path)

                # Move renamed PDF to dated output folder ONLY if DB operations were successful
                if db_success and results and args.output_folder:
                    FileManager.move_to_output(renamed_pdf_path, args.output_folder, log)
                elif not db_success:
                    log.warn(f"{pdf_filename}: DB operations failed - file NOT moved")

            except Exception as e:
                error_msg = f"{pdf_filename}: {e}"
                log.error(error_msg)
                ErrorLogger.log_error("InvoiceExtraction", error_msg, e, logs_folder)

        db.close()
        log.info("all files processed")

    except Exception as e:
        error_msg = f"Fatal error in main execution: {e}"
        log = Logger("Main")
        log.error(error_msg)
        ErrorLogger.log_error("InvoiceExtraction", error_msg, e, logs_folder)
        sys.exit(1)


if __name__ == "__main__":
    main()
"""
Document Extraction Pipeline
=============================
OCR + structured extraction + face/QR extraction for Indian ID / legal documents.
Supports: Aadhaar, PAN, Agreement (fully decomposed legal-agreement schema).

Design:
- OCREngine / StructuredExtractor / FaceExtractor are abstract interfaces -> swap models freely.
- ExtractorFactory + @ExtractorFactory.register() -> add a new document type without touching the pipeline.
- Each schema has field-level validators -> bad OCR output is rejected instead of silently accepted.
- Agreement schema is composed of small, single-responsibility nested Pydantic models (one per
  clause family: parties, dates, money, term, service scope, taxes, termination, dispute
  resolution, IP, confidentiality, data privacy, audit, compliance, code of conduct, schedules,
  signatures/stamps, etc.) instead of one giant flat model.
- FileTypeDetector + PDFPageConverter -> pipeline accepts any supported image format OR a
  multi-page PDF. PDFs are rasterised page-by-page into temp images, OCR'd, combined into a
  single OCR text blob (page-break delimited), structured-extracted ONCE, and the temp page
  images are deleted afterwards.
- FolderDocumentTypeResolver + BatchFolderProcessor -> point at a root folder whose
  sub-folders are named after document types (aadhar/, pan/, agreements/, ...) and every
  image/PDF inside gets identified and processed automatically.
"""

from __future__ import annotations

import difflib
import json
import logging
import os
import re
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional, Tuple, Type, TypeVar, Union

import cv2
import numpy as np
from PIL import Image
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

logger = logging.getLogger("document_pipeline")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@dataclass
class OCRSettings:
    model_path: str = "zai-org/GLM-OCR"
    max_new_tokens: int = 2048
    device_map: str = "auto"
    torch_dtype: str = "float16"  # resolved to a torch.dtype lazily inside GLMOCR


@dataclass
class FaceDetectorSettings:
    repo_id: str = "opencv/face_detection_yunet"
    filename: str = "face_detection_yunet_2023mar.onnx"
    score_threshold: float = 0.7
    nms_threshold: float = 0.3
    top_k: int = 5000
    padding_ratio: float = 0.3
    output_size: Tuple[int, int] = (224, 224)


@dataclass
class PDFSettings:
    dpi: int = 200


@dataclass
class PipelineSettings:
    ocr: OCRSettings = field(default_factory=OCRSettings)
    face: FaceDetectorSettings = field(default_factory=FaceDetectorSettings)
    pdf: PDFSettings = field(default_factory=PDFSettings)
    structured_max_new_tokens: int = 12288  # agreement schema is large -> needs more headroom


settings = PipelineSettings()


# ---------------------------------------------------------------------------
# OCR engine (plug and play)
# ---------------------------------------------------------------------------

class OCREngine(ABC):
    @abstractmethod
    def extract_text(self, image: Union[str, Path, Image.Image], prompt: str) -> str:
        ...

    @abstractmethod
    def generate(self, messages: list, max_new_tokens: int) -> str:
        """Raw chat generation, reused by the structured extractor."""
        ...


class GLMOCR(OCREngine):
    def __init__(self, config: OCRSettings = settings.ocr):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        self.config = config
        self.torch = torch
        dtype = getattr(torch, config.torch_dtype)
        self.processor = AutoProcessor.from_pretrained(config.model_path)
        self.model = AutoModelForImageTextToText.from_pretrained(
            config.model_path, dtype=dtype, device_map=config.device_map
        )
        self.model.eval()

    def extract_text(self, image: Union[str, Path, Image.Image], prompt: str = "Text Recognition:") -> str:
        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")
        messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]}]
        return self.generate(messages, self.config.max_new_tokens)

    def generate(self, messages: list, max_new_tokens: int) -> str:
        inputs = self.processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt"
        )
        inputs = {k: (v.to(self.model.device) if hasattr(v, "to") else v) for k, v in inputs.items()}
        inputs.pop("token_type_ids", None)

        with self.torch.inference_mode():
            generated_ids = self.model.generate(**inputs, max_new_tokens=max_new_tokens)

        input_length = inputs["input_ids"].shape[1]
        return self.processor.decode(generated_ids[0][input_length:], skip_special_tokens=True).strip()


# ---------------------------------------------------------------------------
# Structured extractor (plug and play)
# ---------------------------------------------------------------------------

T = TypeVar("T", bound=BaseModel)


class StructuredExtractor(ABC):
    @abstractmethod
    def extract(self, prompt: str, schema: Type[T]) -> T:
        ...


class GLMStructuredExtractor(StructuredExtractor):
    def __init__(self, ocr: OCREngine, max_new_tokens: int = settings.structured_max_new_tokens):
        self.ocr = ocr
        self.max_new_tokens = max_new_tokens

    def extract(self, prompt: str, schema: Type[T]) -> T:
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        raw = self.ocr.generate(messages, self.max_new_tokens)
        cleaned = self._clean_json(raw)
        data = self._safe_json_loads(cleaned, raw)
        return schema.model_validate(data)

    @staticmethod
    def _clean_json(text: str) -> str:
        text = text.strip()
        text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        # Prefer a proper balanced-brace scan over a greedy first{...}last} match,
        # since the agreement prompt itself contains a large example JSON block that
        # a naive greedy regex could accidentally straddle if the model echoes any of it.
        trimmed = GLMStructuredExtractor._trim_balanced(text)
        if trimmed:
            text = trimmed
        else:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if match:
                text = match.group(0)
        return re.sub(r",\s*([}\]])", r"\1", text).strip()

    @staticmethod
    def _safe_json_loads(cleaned: str, raw: str) -> Dict[str, Any]:
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            trimmed = GLMStructuredExtractor._trim_balanced(cleaned)
            if trimmed:
                try:
                    return json.loads(trimmed)
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Model did not return valid JSON: {e}\nRaw output:\n{raw}") from e

    @staticmethod
    def _trim_balanced(text: str) -> Optional[str]:
        depth = 0
        start = text.find("{")
        if start == -1:
            return None
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        return None


# ---------------------------------------------------------------------------
# Lenient boolean coercion
# ---------------------------------------------------------------------------
# The OCR/structured-extraction model occasionally drops a stray value (a date,
# a fragment of nearby text, etc.) into a boolean-typed field instead of
# true/false. Pydantic's default bool parsing raises ValidationError on any
# string it can't confidently interpret, which would fail the ENTIRE document
# for one bad field. LenientBool coerces common truthy/falsy spellings and
# falls back to None (unknown) for anything else, instead of crashing.

def _coerce_bool(v: Any) -> Optional[bool]:
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    if s in {"true", "yes", "y", "1", "present", "applicable", "allowed", "required", "detected"}:
        return True
    if s in {"false", "no", "n", "0", "", "not present", "not applicable", "not allowed", "not required", "absent"}:
        return False
    return None  # unparseable garbage -> unknown, never crash the whole document


LenientBool = Annotated[Optional[bool], BeforeValidator(_coerce_bool)]


# ---------------------------------------------------------------------------
# Aadhaar / PAN schemas (unchanged)
# ---------------------------------------------------------------------------

class AadhaarDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_type: str = "aadhaar"
    name: Optional[str] = None
    guardian_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    aadhaar_number_masked: Optional[str] = None
    aadhaar_number_unmasked: Optional[str] = None
    vid: Optional[str] = None
    address: Optional[str] = None
    pincode: Optional[str] = None
    enrolment_number: Optional[str] = None
    barcode_qr_code: Optional[str] = None
    barcode_qr_raw_data: Optional[str] = None
    photo_path: Optional[str] = None

    @field_validator("aadhaar_number_unmasked")
    @classmethod
    def validate_aadhaar_number(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        digits = re.sub(r"\D", "", v)
        return digits if len(digits) == 12 else None

    @field_validator("pincode")
    @classmethod
    def validate_pincode(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v if re.fullmatch(r"\d{6}", v) else None

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v if re.fullmatch(r"\d{2}/\d{2}/\d{4}", v) else None


class PANDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_type: str = "pan"
    name: Optional[str] = None
    father_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    pan_number: Optional[str] = None
    signature_present: LenientBool = None
    barcode_qr_code: Optional[str] = None
    barcode_qr_raw_data: Optional[str] = None
    photo_path: Optional[str] = None

    @field_validator("pan_number")
    @classmethod
    def validate_pan(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().upper().replace(" ", "")
        return v if re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", v) else None

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v if re.fullmatch(r"\d{2}/\d{2}/\d{4}", v) else None


# ---------------------------------------------------------------------------
# Agreement schema - decomposed into one small model per clause family.
# Every leaf field is Optional[str] (or a typed list of sub-objects) so a
# missing/unreadable field never breaks validation - it just comes back None.
# ---------------------------------------------------------------------------

class DocumentInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    document_title: Optional[str] = None
    agreement_type: Optional[str] = None
    agreement_number: Optional[str] = None
    agreement_reference_number: Optional[str] = None
    document_version: Optional[str] = None
    document_status: Optional[str] = None
    execution_location: Optional[str] = None
    execution_date: Optional[str] = None
    effective_date: Optional[str] = None
    commencement_date: Optional[str] = None
    agreement_date: Optional[str] = None


class CompanyParty(BaseModel):
    model_config = ConfigDict(extra="ignore")
    company_name: Optional[str] = None
    company_type: Optional[str] = None
    company_registration_number: Optional[str] = None
    corporate_identification_number: Optional[str] = None
    pan: Optional[str] = None
    gstin: Optional[str] = None
    registered_address: Optional[str] = None
    corporate_address: Optional[str] = None
    branch_address: Optional[str] = None
    contact_person: Optional[str] = None
    designation: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    authorized_signatory_name: Optional[str] = None
    authorized_signatory_designation: Optional[str] = None
    authorization_type: Optional[str] = None
    board_resolution_date: Optional[str] = None
    power_of_attorney_date: Optional[str] = None
    company_registered_under: Optional[str] = None
    regulatory_authority: Optional[str] = None
    banking_license_information: Optional[str] = None


class IndividualDetails(BaseModel):
    model_config = ConfigDict(extra="ignore")
    individual_name: Optional[str] = None
    parent_or_spouse_name: Optional[str] = None
    pan: Optional[str] = None
    residential_address: Optional[str] = None


class ProprietorshipDetails(BaseModel):
    model_config = ConfigDict(extra="ignore")
    proprietor_name: Optional[str] = None
    proprietorship_name: Optional[str] = None
    proprietor_pan: Optional[str] = None
    business_address: Optional[str] = None


class HUFDetails(BaseModel):
    model_config = ConfigDict(extra="ignore")
    huf_name: Optional[str] = None
    karta_name: Optional[str] = None
    karta_pan: Optional[str] = None
    huf_address: Optional[str] = None


class PartnershipDetails(BaseModel):
    model_config = ConfigDict(extra="ignore")
    firm_name: Optional[str] = None
    firm_pan: Optional[str] = None
    registration_number: Optional[str] = None
    registration_date: Optional[str] = None
    registered_office: Optional[str] = None
    partner_name: Optional[str] = None
    partner_pan: Optional[str] = None
    partner_authorization: Optional[str] = None
    poa_date: Optional[str] = None


class CompanyEntityDetails(BaseModel):
    model_config = ConfigDict(extra="ignore")
    legal_name: Optional[str] = None
    cin: Optional[str] = None
    pan: Optional[str] = None
    registered_office: Optional[str] = None
    director_name: Optional[str] = None
    director_designation: Optional[str] = None
    board_resolution_date: Optional[str] = None
    authorized_representative: Optional[str] = None


class ServiceProviderParty(BaseModel):
    model_config = ConfigDict(extra="ignore")
    service_provider_name: Optional[str] = None
    service_provider_type: Optional[str] = None
    individual_or_entity: Optional[str] = None  # individual/proprietorship/huf/partnership_firm/private_limited_company/public_limited_company/llp/other_entity
    father_mother_spouse_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    pan: Optional[str] = None
    aadhaar: Optional[str] = None
    gstin: Optional[str] = None
    registration_number: Optional[str] = None
    registered_address: Optional[str] = None
    residential_address: Optional[str] = None
    business_address: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    alternate_phone: Optional[str] = None
    contact_person: Optional[str] = None
    designation: Optional[str] = None
    individual: Optional[IndividualDetails] = None
    proprietorship: Optional[ProprietorshipDetails] = None
    huf: Optional[HUFDetails] = None
    partnership: Optional[PartnershipDetails] = None
    company: Optional[CompanyEntityDetails] = None

    @field_validator("aadhaar")
    @classmethod
    def validate_aadhaar(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        digits = re.sub(r"\D", "", v)
        return digits if len(digits) == 12 else v  # keep masked form as-is, only strip junk from full numbers

    @field_validator("pan")
    @classmethod
    def validate_pan(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().upper().replace(" ", "")
        return v if re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", v) else None


class PartyRepresentative(BaseModel):
    model_config = ConfigDict(extra="ignore")
    role: Optional[str] = None  # e.g. "company" | "service_provider" | "witness"
    name: Optional[str] = None
    designation: Optional[str] = None
    contact: Optional[str] = None


class DateEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    date_type: str  # agreement_date/effective_date/termination_notice_date/board_resolution_date/... (see DATE_TYPES)
    date_value: Optional[str] = None
    date_text_original: Optional[str] = None
    related_clause: Optional[str] = None
    event: Optional[str] = None
    page_number: Optional[int] = None
    clause_number: Optional[str] = None
    date_confidence: Optional[str] = None

    @field_validator("date_value")
    @classmethod
    def validate_date_value(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v if re.fullmatch(r"\d{2}/\d{2}/\d{4}", v) else None


class MonetaryValue(BaseModel):
    model_config = ConfigDict(extra="ignore")
    amount: Optional[float] = None
    currency: str = "INR"
    amount_text: Optional[str] = None
    amount_type: str  # STAMP_DUTY/SERVICE_FEE/REFERRAL_FEE/COMMISSION/LOAN_AMOUNT/... (see MONEY_TYPES)
    payment_direction: Optional[str] = None
    frequency: Optional[str] = None
    basis: Optional[str] = None
    tax_treatment: Optional[str] = None
    page: Optional[str] = None
    clause: Optional[str] = None

    @field_validator("amount", mode="before")
    @classmethod
    def coerce_amount(cls, v):
        if v in (None, ""):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        digits = re.sub(r"[^\d.]", "", str(v))
        try:
            return float(digits) if digits else None
        except ValueError:
            return None


class PercentageFee(BaseModel):
    model_config = ConfigDict(extra="ignore")
    fee_percentage: Optional[str] = None
    percentage_value: Optional[float] = None
    percentage_basis: Optional[str] = None
    percentage_of: Optional[str] = None
    fee_calculation_method: Optional[str] = None
    condition: Optional[str] = None

    @field_validator("percentage_value", mode="before")
    @classmethod
    def coerce_percentage(cls, v):
        if v in (None, ""):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        digits = re.sub(r"[^\d.]", "", str(v))
        try:
            return float(digits) if digits else None
        except ValueError:
            return None


class TermAndRenewal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    term_type: Optional[str] = None
    term_duration: Optional[str] = None
    term_duration_unit: Optional[str] = None
    effective_date: Optional[str] = None
    commencement_date: Optional[str] = None
    expiry_date: Optional[str] = None
    end_date: Optional[str] = None
    renewal_type: Optional[str] = None
    renewal_period: Optional[str] = None
    automatic_renewal: LenientBool = None
    renewal_notice_period: Optional[str] = None
    extension_conditions: Optional[str] = None


class ServiceScope(BaseModel):
    model_config = ConfigDict(extra="ignore")
    service_scope: Optional[str] = None
    services_description: Optional[str] = None
    service_category: Optional[str] = None
    service_location: Optional[str] = None
    service_provider_obligations: Optional[str] = None
    company_obligations: Optional[str] = None
    referral_activities: Optional[str] = None
    customer_acquisition_activities: Optional[str] = None
    lead_generation: Optional[str] = None
    marketing_activities: Optional[str] = None
    documentation_assistance: Optional[str] = None
    customer_verification: Optional[str] = None
    KYC_activity: Optional[str] = None
    loan_referral_activity: Optional[str] = None


class ReferralInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    referral_program: Optional[str] = None
    referral_agent: Optional[str] = None
    referral_source: Optional[str] = None
    lead: Optional[str] = None
    prospective_customer: Optional[str] = None
    customer_name: Optional[str] = None
    customer_contact: Optional[str] = None
    referral_date: Optional[str] = None
    lead_date: Optional[str] = None
    lead_status: Optional[str] = None
    customer_eligibility: Optional[str] = None
    loan_application: Optional[str] = None
    loan_application_date: Optional[str] = None
    loan_approval_date: Optional[str] = None
    loan_disbursement_date: Optional[str] = None
    loan_disbursement_amount: Optional[str] = None
    processing_fee: Optional[str] = None
    referral_fee: Optional[str] = None
    referral_commission: Optional[str] = None


class LoanInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    loan_amount: Optional[str] = None
    sanctioned_amount: Optional[str] = None
    approved_amount: Optional[str] = None
    disbursed_amount: Optional[str] = None
    disbursement_amount: Optional[str] = None
    loan_processing_fee: Optional[str] = None
    processing_fee_percentage: Optional[str] = None
    processing_fee_amount: Optional[str] = None
    interest_rate: Optional[str] = None
    interest_amount: Optional[str] = None
    loan_tenure: Optional[str] = None
    loan_currency: Optional[str] = "INR"


class PaymentTerms(BaseModel):
    model_config = ConfigDict(extra="ignore")
    payment_frequency: Optional[str] = None
    payment_cycle: Optional[str] = None
    invoice_required: LenientBool = None
    invoice_submission_period: Optional[str] = None
    invoice_due_period: Optional[str] = None
    payment_due_days: Optional[str] = None
    payment_due_date: Optional[str] = None
    payment_method: Optional[str] = None
    payment_account: Optional[str] = None
    bank_account: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc: Optional[str] = None
    payment_conditions: Optional[str] = None
    payment_dependencies: Optional[str] = None
    tax_deductions: Optional[str] = None

    @field_validator("ifsc")
    @classmethod
    def validate_ifsc(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().upper()
        return v if re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", v) else None


class TaxInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tax_applicable: LenientBool = None
    tax_type: Optional[str] = None
    gst_applicable: LenientBool = None
    gst_rate: Optional[str] = None
    gst_amount: Optional[str] = None
    tds_applicable: LenientBool = None
    tds_rate: Optional[str] = None
    tds_amount: Optional[str] = None
    withholding_tax: Optional[str] = None
    tax_deduction_at_source: Optional[str] = None
    tax_registration_number: Optional[str] = None
    pan: Optional[str] = None
    gstin: Optional[str] = None
    tax_invoice_requirement: Optional[str] = None
    tax_deduction_clause: Optional[str] = None


class ObligationsRightsConditions(BaseModel):
    model_config = ConfigDict(extra="ignore")
    obligations: Optional[str] = None
    rights: Optional[str] = None
    conditions_precedent: Optional[str] = None


class RepresentationsWarranties(BaseModel):
    model_config = ConfigDict(extra="ignore")
    authority_to_execute: Optional[str] = None
    legal_capacity: Optional[str] = None
    regulatory_compliance: Optional[str] = None
    no_conflict: Optional[str] = None
    no_litigation: Optional[str] = None
    accuracy_of_information: Optional[str] = None
    license_validity: Optional[str] = None
    anti_bribery: Optional[str] = None
    anti_corruption: Optional[str] = None
    data_compliance: Optional[str] = None
    tax_compliance: Optional[str] = None


class ConfidentialityInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    confidential_information_definition: Optional[str] = None
    confidentiality_obligation: Optional[str] = None
    confidentiality_start_date: Optional[str] = None
    confidentiality_end_date: Optional[str] = None
    confidentiality_survival_period: Optional[str] = None
    permitted_disclosure: Optional[str] = None
    required_disclosure: Optional[str] = None
    data_protection_obligation: Optional[str] = None
    return_or_destruction_of_information: Optional[str] = None


class DataPrivacyInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    personal_data: Optional[str] = None
    customer_data: Optional[str] = None
    data_processing: Optional[str] = None
    data_security: Optional[str] = None
    data_access: Optional[str] = None
    data_storage: Optional[str] = None
    data_retention: Optional[str] = None
    data_deletion: Optional[str] = None
    privacy_obligation: Optional[str] = None
    data_breach: Optional[str] = None
    breach_notification: Optional[str] = None


class IntellectualPropertyInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    ip_owner: Optional[str] = None
    intellectual_property_type: Optional[str] = None
    pre_existing_ip: Optional[str] = None
    new_ip: Optional[str] = None
    created_ip: Optional[str] = None
    license_granted: Optional[str] = None
    license_scope: Optional[str] = None
    license_duration: Optional[str] = None
    license_territory: Optional[str] = None
    copyright: Optional[str] = None
    trademark: Optional[str] = None
    trade_secret: Optional[str] = None
    ownership_transfer: Optional[str] = None


class AuditInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    audit_right: Optional[str] = None
    audit_frequency: Optional[str] = None
    inspection_right: Optional[str] = None
    inspection_notice: Optional[str] = None
    records_retention_period: Optional[str] = None
    record_access: Optional[str] = None
    compliance_review: Optional[str] = None
    audit_cost: Optional[str] = None
    audit_obligation: Optional[str] = None


class ComplianceInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    applicable_law: Optional[str] = None
    regulatory_authority: Optional[str] = None
    RBI_requirement: Optional[str] = None
    banking_regulation: Optional[str] = None
    KYC_requirement: Optional[str] = None
    AML_requirement: Optional[str] = None
    anti_money_laundering: Optional[str] = None
    customer_protection: Optional[str] = None
    regulatory_reporting: Optional[str] = None
    license_requirement: Optional[str] = None
    statutory_compliance: Optional[str] = None


class IndemnificationInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    indemnity_exists: LenientBool = None
    indemnifying_party: Optional[str] = None
    indemnified_party: Optional[str] = None
    indemnity_scope: Optional[str] = None
    indemnifiable_loss: Optional[str] = None
    third_party_claim: Optional[str] = None
    legal_costs: Optional[str] = None
    tax_loss: Optional[str] = None
    regulatory_loss: Optional[str] = None
    fraud: Optional[str] = None
    negligence: Optional[str] = None
    breach_of_contract: Optional[str] = None
    indemnity_limit: Optional[str] = None
    indemnity_exclusions: Optional[str] = None


class LiabilityInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    liability_clause: Optional[str] = None
    liability_cap: Optional[str] = None
    liability_cap_amount: Optional[str] = None
    liability_cap_currency: Optional[str] = "INR"
    unlimited_liability: LenientBool = None
    excluded_losses: Optional[str] = None
    indirect_loss: Optional[str] = None
    consequential_loss: Optional[str] = None
    loss_of_profit: Optional[str] = None
    loss_of_business: Optional[str] = None
    liability_exceptions: Optional[str] = None


class InsuranceInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    insurance_required: LenientBool = None
    insurance_type: Optional[str] = None
    coverage_amount: Optional[str] = None
    coverage_currency: Optional[str] = "INR"
    policy_period: Optional[str] = None
    insurer: Optional[str] = None
    policy_number: Optional[str] = None
    renewal_requirement: Optional[str] = None
    proof_of_insurance: Optional[str] = None


class ForceMajeureInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    force_majeure_applicable: LenientBool = None
    force_majeure_events: Optional[str] = None
    notice_requirement: Optional[str] = None
    force_majeure_start_date: Optional[str] = None
    force_majeure_end_date: Optional[str] = None
    suspension_period: Optional[str] = None
    termination_after_force_majeure: Optional[str] = None


class TerminationInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    termination_allowed: LenientBool = None
    termination_type: Optional[str] = None
    termination_for_convenience: Optional[str] = None
    termination_for_cause: Optional[str] = None
    termination_for_breach: Optional[str] = None
    termination_for_insolvency: Optional[str] = None
    termination_for_change_of_control: Optional[str] = None
    termination_for_regulatory_reason: Optional[str] = None
    termination_notice_period: Optional[str] = None
    termination_notice_unit: Optional[str] = None
    termination_event: Optional[str] = None
    termination_trigger: Optional[str] = None
    termination_effective_date: Optional[str] = None
    cure_period: Optional[str] = None
    post_termination_obligations: Optional[str] = None
    survival_clauses: Optional[str] = None


class NoticeInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    notice_required: LenientBool = None
    notice_period: Optional[str] = None
    notice_period_unit: Optional[str] = None
    notice_method: Optional[str] = None
    notice_address: Optional[str] = None
    notice_email: Optional[str] = None
    notice_recipient: Optional[str] = None
    notice_effective_rule: Optional[str] = None
    notice_delivery_method: Optional[str] = None


class AssignmentSubcontractingInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    assignment_allowed: LenientBool = None
    assignment_by_company: Optional[str] = None
    assignment_by_service_provider: Optional[str] = None
    prior_consent_required: LenientBool = None
    assignment_consent_type: Optional[str] = None
    change_of_control: Optional[str] = None
    subcontracting_allowed: LenientBool = None
    subcontracting_consent: Optional[str] = None
    subcontractor_consent: Optional[str] = None
    subcontractor_requirements: Optional[str] = None
    subcontractor_liability: Optional[str] = None
    subcontractor_confidentiality: Optional[str] = None


class DisputeResolutionInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    dispute_resolution_method: Optional[str] = None
    negotiation_period: Optional[str] = None
    mediation: Optional[str] = None
    arbitration: Optional[str] = None
    arbitration_notice: Optional[str] = None
    arbitration_seat: Optional[str] = None
    arbitration_venue: Optional[str] = None
    arbitration_language: Optional[str] = None
    arbitrator_appointment: Optional[str] = None
    dispute_notice_period: Optional[str] = None


class GoverningLawInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    governing_law: Optional[str] = None
    jurisdiction: Optional[str] = None
    exclusive_jurisdiction: LenientBool = None
    courts: Optional[str] = None
    arbitration_rules: Optional[str] = None
    arbitrator: Optional[str] = None


class MiscellaneousInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    entire_agreement: Optional[str] = None
    amendment: Optional[str] = None
    modification: Optional[str] = None
    waiver: Optional[str] = None
    severability: Optional[str] = None
    counterparts: Optional[str] = None
    electronic_signature: Optional[str] = None
    relationship_of_parties: Optional[str] = None
    independent_contractor: Optional[str] = None
    no_agency: Optional[str] = None
    no_partnership: Optional[str] = None
    survival: Optional[str] = None
    further_assurance: Optional[str] = None
    costs_and_expenses: Optional[str] = None
    stamp_duty: Optional[str] = None


class ScheduleEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schedule_type: Optional[str] = None  # schedule/annexure/appendix/exhibit/attachment
    schedule_number: str
    schedule_title: Optional[str] = None
    schedule_content: Optional[str] = None


class StampInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    stamp_present: LenientBool = None
    stamp_type: Optional[str] = None
    stamp_value: Optional[str] = None
    stamp_currency: Optional[str] = "INR"
    stamp_state: Optional[str] = None
    stamp_serial_number: Optional[str] = None
    stamp_issue_date: Optional[str] = None
    stamp_authority: Optional[str] = None
    notary_present: LenientBool = None
    notary_name: Optional[str] = None
    notary_date: Optional[str] = None
    notary_registration_number: Optional[str] = None


class Signatory(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    designation: Optional[str] = None
    signature_present: LenientBool = None
    signature_date: Optional[str] = None


class SignatureBlock(BaseModel):
    model_config = ConfigDict(extra="ignore")
    company_signatory: Optional[Signatory] = None
    service_provider_signatory: Optional[Signatory] = None
    witness_1_name: Optional[str] = None
    witness_1_signature: LenientBool = None
    witness_2_name: Optional[str] = None
    witness_2_signature: LenientBool = None
    rubber_stamp_present: LenientBool = None
    company_stamp_present: LenientBool = None
    service_provider_stamp_present: LenientBool = None
    stamp_text: Optional[str] = None
    stamp_location: Optional[str] = None


class CodeOfConductInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    code_of_conduct: Optional[str] = None
    customer_interaction_rules: Optional[str] = None
    calling_restrictions: Optional[str] = None
    communication_restrictions: Optional[str] = None
    lead_generation_rules: Optional[str] = None
    misrepresentation_prohibited: LenientBool = None
    false_promise_prohibited: LenientBool = None
    customer_consent: Optional[str] = None
    data_collection_rules: Optional[str] = None
    record_keeping: Optional[str] = None
    follow_up_rules: Optional[str] = None
    professional_conduct: Optional[str] = None
    prohibited_practices: Optional[str] = None


class ClauseMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")
    clause_number: Optional[str] = None
    clause_title: Optional[str] = None
    page_number: Optional[int] = None
    extraction_evidence: Optional[str] = None  # short verbatim-free pointer to where this was found


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")
    page_count: Optional[int] = None
    total_clauses_detected: Optional[int] = None
    extraction_notes: Optional[str] = None


DATE_TYPES = [
    "agreement_date", "execution_date", "effective_date", "commencement_date", "start_date",
    "end_date", "expiry_date", "termination_date", "renewal_date", "renewal_effective_date",
    "company_signature_date", "service_provider_signature_date", "authorized_signatory_signature_date",
    "witness_signature_date", "stamp_date", "board_resolution_date", "power_of_attorney_date",
    "partner_authorization_date", "designated_partner_resolution_date", "invoice_date",
    "invoice_submission_date", "payment_due_date", "payment_date", "payment_cycle_date",
    "month_end_date", "tax_deduction_date", "notice_date", "notice_effective_date",
    "notice_period_start_date", "notice_period_end_date", "termination_notice_date", "audit_date",
    "inspection_date", "review_date", "kyc_review_date", "periodic_review_date",
    "compliance_deadline", "service_start_date", "service_completion_date",
    "loan_disbursement_date", "referral_date", "lead_date", "customer_contact_date",
    "approval_date", "amendment_date", "variation_date", "supplement_date", "novation_date",
    "renewal_agreement_date",
]

MONEY_TYPES = [
    "STAMP_DUTY", "REGISTRATION_FEE", "SERVICE_FEE", "SERVICE_CHARGE", "REFERRAL_FEE",
    "COMMISSION", "PROCESSING_FEE", "PROFESSIONAL_FEE", "FIXED_FEE", "VARIABLE_FEE",
    "PERCENTAGE_FEE", "LOAN_AMOUNT", "DISBURSEMENT_AMOUNT", "CUSTOMER_PAYMENT",
    "REIMBURSEMENT", "EXPENSE", "PENALTY", "LIQUIDATED_DAMAGES", "INTEREST", "TAX", "GST",
    "TDS", "WITHHOLDING_TAX", "SECURITY_DEPOSIT", "ADVANCE", "REFUND", "CREDIT", "DEBIT",
    "OTHER",
]


class AgreementDocument(BaseModel):
    """Fully decomposed schema for legal / rental / sale / service-referral agreements
    (often multi-page PDFs). Each clause family is its own nested model so a bad or
    missing sub-section never invalidates the rest of the document."""

    model_config = ConfigDict(extra="ignore")

    document_type: str = "agreement"

    document_info: DocumentInfo = Field(default_factory=DocumentInfo)
    company: CompanyParty = Field(default_factory=CompanyParty)
    service_provider: ServiceProviderParty = Field(default_factory=ServiceProviderParty)
    party_representatives: List[PartyRepresentative] = Field(default_factory=list)

    dates: List[DateEntry] = Field(default_factory=list)
    monetary_values: List[MonetaryValue] = Field(default_factory=list)
    percentage_fees: List[PercentageFee] = Field(default_factory=list)

    term_and_renewal: TermAndRenewal = Field(default_factory=TermAndRenewal)
    services: ServiceScope = Field(default_factory=ServiceScope)
    referrals: ReferralInfo = Field(default_factory=ReferralInfo)
    loan_information: LoanInfo = Field(default_factory=LoanInfo)
    payment_terms: PaymentTerms = Field(default_factory=PaymentTerms)
    taxes: TaxInfo = Field(default_factory=TaxInfo)

    obligations_rights_conditions: ObligationsRightsConditions = Field(default_factory=ObligationsRightsConditions)
    representations_warranties: RepresentationsWarranties = Field(default_factory=RepresentationsWarranties)
    confidentiality: ConfidentialityInfo = Field(default_factory=ConfidentialityInfo)
    data_privacy: DataPrivacyInfo = Field(default_factory=DataPrivacyInfo)
    intellectual_property: IntellectualPropertyInfo = Field(default_factory=IntellectualPropertyInfo)
    audit: AuditInfo = Field(default_factory=AuditInfo)
    compliance: ComplianceInfo = Field(default_factory=ComplianceInfo)
    indemnification: IndemnificationInfo = Field(default_factory=IndemnificationInfo)
    liability: LiabilityInfo = Field(default_factory=LiabilityInfo)
    insurance: InsuranceInfo = Field(default_factory=InsuranceInfo)
    force_majeure: ForceMajeureInfo = Field(default_factory=ForceMajeureInfo)
    termination: TerminationInfo = Field(default_factory=TerminationInfo)
    notices: NoticeInfo = Field(default_factory=NoticeInfo)
    assignment_subcontracting: AssignmentSubcontractingInfo = Field(default_factory=AssignmentSubcontractingInfo)
    dispute_resolution: DisputeResolutionInfo = Field(default_factory=DisputeResolutionInfo)
    governing_law: GoverningLawInfo = Field(default_factory=GoverningLawInfo)
    miscellaneous: MiscellaneousInfo = Field(default_factory=MiscellaneousInfo)
    code_of_conduct: CodeOfConductInfo = Field(default_factory=CodeOfConductInfo)

    schedules: List[ScheduleEntry] = Field(default_factory=list)
    stamp: StampInfo = Field(default_factory=StampInfo)
    signatures: SignatureBlock = Field(default_factory=SignatureBlock)

    clause_metadata: List[ClauseMetadata] = Field(default_factory=list)
    document_metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)

    # legacy flat fields kept for backward compatibility with earlier callers
    barcode_qr_code: Optional[str] = None
    barcode_qr_raw_data: Optional[str] = None
    photo_path: Optional[str] = None
    page_count: Optional[int] = None


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

AADHAAR_EXTRACTION_PROMPT = r"""
You are an Indian Aadhaar card document extraction system.
Extract information from the OCR text provided below.
Return ONLY valid JSON. No markdown, no explanations, no invented values.
If a field is not present or not confidently readable, return null.

CRITICAL RULES:
1. The Aadhaar number is labeled "Your Aadhaar No." or similar.
2. Aadhaar number format is 12 digits, often masked as "xxxx xxxx 1234".
3. Do not confuse the Aadhaar number with the Enrolment Number, VID, or a phone number.
4. Extract the masked Aadhaar number as "aadhaar_number_masked".
5. Extract the full 12-digit number if available as "aadhaar_number_unmasked".

The JSON must contain exactly these fields:
{{
  "document_type": "aadhaar",
  "name": null,
  "guardian_name": null,
  "date_of_birth": null,
  "gender": null,
  "aadhaar_number_masked": null,
  "aadhaar_number_unmasked": null,
  "vid": null,
  "address": null,
  "pincode": null,
  "enrolment_number": null,
  "barcode_qr_code": null,
  "barcode_qr_raw_data": null
}}

OCR TEXT:
<<<OCR_TEXT>>>
{ocr_text}
<<<END_OCR_TEXT>>>
"""

PAN_EXTRACTION_PROMPT = r"""
You are an Indian PAN card document extraction system.
Extract information from the OCR text provided below.
Return ONLY valid JSON. No markdown, no explanations, no invented values.
If a field is not present, return null.

CRITICAL RULES:
1. PAN number format is 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F).
2. Do not confuse PAN number with Aadhaar-linked reference numbers.

The JSON must contain exactly these fields:
{{
  "document_type": "pan",
  "name": null,
  "father_name": null,
  "date_of_birth": null,
  "pan_number": null,
  "signature_present": null
}}

OCR TEXT:
<<<OCR_TEXT>>>
{ocr_text}
<<<END_OCR_TEXT>>>
"""

AGREEMENT_EXTRACTION_PROMPT = r"""
You are a legal agreement document extraction system specialised in Indian financial /
service / referral agreements (e.g. bank <-> referral agent agreements).
Extract information from the OCR text of a (possibly multi-page) agreement below.
Return ONLY valid JSON matching the schema below. No markdown, no explanations, no
invented values - if a field is not present or not confidently readable, use null
(or an empty list [] for list fields).

CRITICAL RULES:
1. The text may span multiple pages separated by "----- PAGE BREAK -----" - read across all of them.
2. Create a SEPARATE object for each party (do not flatten company and service-provider fields together).
3. "service_provider.individual_or_entity" must be one of: individual, proprietorship, huf,
   partnership_firm, private_limited_company, public_limited_company, llp, other_entity.
   Populate ONLY the matching sub-object (individual / proprietorship / huf / partnership / company)
   under "service_provider" based on that value; leave the others null.
4. Do NOT use a single flat "date" field. Every date found must become one entry in the "dates"
   list with a "date_type" from this set: {date_types}.
   Preserve the original printed text in "date_text_original" even when you also normalise it
   into "date_value" (DD/MM/YYYY). E.g. "25th day of March 2026" -> date_value "25/03/2026",
   date_text_original "25th day of March 2026".
5. Do NOT use a single flat "amount" field. Every monetary value found must become one entry in
   the "monetary_values" list with an "amount_type" from this set: {money_types}.
   A visible non-judicial stamp paper value (e.g. "Rs.100") must be classified as
   amount_type "STAMP_DUTY", NOT as a service fee.
6. Percentage-based fees (e.g. "X% of processing fee collected on loans disbursed") go in
   "percentage_fees", not in "monetary_values" - do not extract a bare percentage as money.
7. Capture every schedule / annexure / appendix / exhibit found as one entry in "schedules"
   with its own "schedule_number" and a concise "schedule_content" summary - do not skip them.
8. "party_1_name"/"party_2_name" style flat fields are NOT used - the Company goes in "company",
   the Service Provider / Referral Agent goes in "service_provider".
9. Capture party names, designations and addresses exactly as printed; do not invent titles.
10. For every clause you can locate a clause/section number for, add an entry to "clause_metadata".

JSON SCHEMA (populate every key; use null / [] where information is absent):
{{
  "document_type": "agreement",
  "document_info": {{
    "document_title": null, "agreement_type": null, "agreement_number": null,
    "agreement_reference_number": null, "document_version": null, "document_status": null,
    "execution_location": null, "execution_date": null, "effective_date": null,
    "commencement_date": null, "agreement_date": null
  }},
  "company": {{
    "company_name": null, "company_type": null, "company_registration_number": null,
    "corporate_identification_number": null, "pan": null, "gstin": null,
    "registered_address": null, "corporate_address": null, "branch_address": null,
    "contact_person": null, "designation": null, "email": null, "phone": null,
    "authorized_signatory_name": null, "authorized_signatory_designation": null,
    "authorization_type": null, "board_resolution_date": null, "power_of_attorney_date": null,
    "company_registered_under": null, "regulatory_authority": null, "banking_license_information": null
  }},
  "service_provider": {{
    "service_provider_name": null, "service_provider_type": null, "individual_or_entity": null,
    "father_mother_spouse_name": null, "date_of_birth": null, "pan": null, "aadhaar": null,
    "gstin": null, "registration_number": null, "registered_address": null,
    "residential_address": null, "business_address": null, "email": null, "mobile": null,
    "alternate_phone": null, "contact_person": null, "designation": null,
    "individual": null, "proprietorship": null, "huf": null, "partnership": null, "company": null
  }},
  "party_representatives": [],
  "dates": [{{"date_type": "", "date_value": null, "date_text_original": null, "related_clause": null, "event": null, "page_number": null, "clause_number": null, "date_confidence": null}}],
  "monetary_values": [{{"amount": null, "currency": "INR", "amount_text": null, "amount_type": "", "payment_direction": null, "frequency": null, "basis": null, "tax_treatment": null, "page": null, "clause": null}}],
  "percentage_fees": [{{"fee_percentage": null, "percentage_value": null, "percentage_basis": null, "percentage_of": null, "fee_calculation_method": null, "condition": null}}],
  "term_and_renewal": {{"term_type": null, "term_duration": null, "term_duration_unit": null, "effective_date": null, "commencement_date": null, "expiry_date": null, "end_date": null, "renewal_type": null, "renewal_period": null, "automatic_renewal": null, "renewal_notice_period": null, "extension_conditions": null}},
  "services": {{"service_scope": null, "services_description": null, "service_category": null, "service_location": null, "service_provider_obligations": null, "company_obligations": null, "referral_activities": null, "customer_acquisition_activities": null, "lead_generation": null, "marketing_activities": null, "documentation_assistance": null, "customer_verification": null, "KYC_activity": null, "loan_referral_activity": null}},
  "referrals": {{"referral_program": null, "referral_agent": null, "referral_source": null, "lead": null, "prospective_customer": null, "customer_name": null, "customer_contact": null, "referral_date": null, "lead_date": null, "lead_status": null, "customer_eligibility": null, "loan_application": null, "loan_application_date": null, "loan_approval_date": null, "loan_disbursement_date": null, "loan_disbursement_amount": null, "processing_fee": null, "referral_fee": null, "referral_commission": null}},
  "loan_information": {{"loan_amount": null, "sanctioned_amount": null, "approved_amount": null, "disbursed_amount": null, "disbursement_amount": null, "loan_processing_fee": null, "processing_fee_percentage": null, "processing_fee_amount": null, "interest_rate": null, "interest_amount": null, "loan_tenure": null, "loan_currency": "INR"}},
  "payment_terms": {{"payment_frequency": null, "payment_cycle": null, "invoice_required": null, "invoice_submission_period": null, "invoice_due_period": null, "payment_due_days": null, "payment_due_date": null, "payment_method": null, "payment_account": null, "bank_account": null, "bank_name": null, "account_number": null, "ifsc": null, "payment_conditions": null, "payment_dependencies": null, "tax_deductions": null}},
  "taxes": {{"tax_applicable": null, "tax_type": null, "gst_applicable": null, "gst_rate": null, "gst_amount": null, "tds_applicable": null, "tds_rate": null, "tds_amount": null, "withholding_tax": null, "tax_deduction_at_source": null, "tax_registration_number": null, "pan": null, "gstin": null, "tax_invoice_requirement": null, "tax_deduction_clause": null}},
  "obligations_rights_conditions": {{"obligations": null, "rights": null, "conditions_precedent": null}},
  "representations_warranties": {{"authority_to_execute": null, "legal_capacity": null, "regulatory_compliance": null, "no_conflict": null, "no_litigation": null, "accuracy_of_information": null, "license_validity": null, "anti_bribery": null, "anti_corruption": null, "data_compliance": null, "tax_compliance": null}},
  "confidentiality": {{"confidential_information_definition": null, "confidentiality_obligation": null, "confidentiality_start_date": null, "confidentiality_end_date": null, "confidentiality_survival_period": null, "permitted_disclosure": null, "required_disclosure": null, "data_protection_obligation": null, "return_or_destruction_of_information": null}},
  "data_privacy": {{"personal_data": null, "customer_data": null, "data_processing": null, "data_security": null, "data_access": null, "data_storage": null, "data_retention": null, "data_deletion": null, "privacy_obligation": null, "data_breach": null, "breach_notification": null}},
  "intellectual_property": {{"ip_owner": null, "intellectual_property_type": null, "pre_existing_ip": null, "new_ip": null, "created_ip": null, "license_granted": null, "license_scope": null, "license_duration": null, "license_territory": null, "copyright": null, "trademark": null, "trade_secret": null, "ownership_transfer": null}},
  "audit": {{"audit_right": null, "audit_frequency": null, "inspection_right": null, "inspection_notice": null, "records_retention_period": null, "record_access": null, "compliance_review": null, "audit_cost": null, "audit_obligation": null}},
  "compliance": {{"applicable_law": null, "regulatory_authority": null, "RBI_requirement": null, "banking_regulation": null, "KYC_requirement": null, "AML_requirement": null, "anti_money_laundering": null, "customer_protection": null, "regulatory_reporting": null, "license_requirement": null, "statutory_compliance": null}},
  "indemnification": {{"indemnity_exists": null, "indemnifying_party": null, "indemnified_party": null, "indemnity_scope": null, "indemnifiable_loss": null, "third_party_claim": null, "legal_costs": null, "tax_loss": null, "regulatory_loss": null, "fraud": null, "negligence": null, "breach_of_contract": null, "indemnity_limit": null, "indemnity_exclusions": null}},
  "liability": {{"liability_clause": null, "liability_cap": null, "liability_cap_amount": null, "liability_cap_currency": "INR", "unlimited_liability": null, "excluded_losses": null, "indirect_loss": null, "consequential_loss": null, "loss_of_profit": null, "loss_of_business": null, "liability_exceptions": null}},
  "insurance": {{"insurance_required": null, "insurance_type": null, "coverage_amount": null, "coverage_currency": "INR", "policy_period": null, "insurer": null, "policy_number": null, "renewal_requirement": null, "proof_of_insurance": null}},
  "force_majeure": {{"force_majeure_applicable": null, "force_majeure_events": null, "notice_requirement": null, "force_majeure_start_date": null, "force_majeure_end_date": null, "suspension_period": null, "termination_after_force_majeure": null}},
  "termination": {{"termination_allowed": null, "termination_type": null, "termination_for_convenience": null, "termination_for_cause": null, "termination_for_breach": null, "termination_for_insolvency": null, "termination_for_change_of_control": null, "termination_for_regulatory_reason": null, "termination_notice_period": null, "termination_notice_unit": null, "termination_event": null, "termination_trigger": null, "termination_effective_date": null, "cure_period": null, "post_termination_obligations": null, "survival_clauses": null}},
  "notices": {{"notice_required": null, "notice_period": null, "notice_period_unit": null, "notice_method": null, "notice_address": null, "notice_email": null, "notice_recipient": null, "notice_effective_rule": null, "notice_delivery_method": null}},
  "assignment_subcontracting": {{"assignment_allowed": null, "assignment_by_company": null, "assignment_by_service_provider": null, "prior_consent_required": null, "assignment_consent_type": null, "change_of_control": null, "subcontracting_allowed": null, "subcontracting_consent": null, "subcontractor_consent": null, "subcontractor_requirements": null, "subcontractor_liability": null, "subcontractor_confidentiality": null}},
  "dispute_resolution": {{"dispute_resolution_method": null, "negotiation_period": null, "mediation": null, "arbitration": null, "arbitration_notice": null, "arbitration_seat": null, "arbitration_venue": null, "arbitration_language": null, "arbitrator_appointment": null, "dispute_notice_period": null}},
  "governing_law": {{"governing_law": null, "jurisdiction": null, "exclusive_jurisdiction": null, "courts": null, "arbitration_rules": null, "arbitrator": null}},
  "miscellaneous": {{"entire_agreement": null, "amendment": null, "modification": null, "waiver": null, "severability": null, "counterparts": null, "electronic_signature": null, "relationship_of_parties": null, "independent_contractor": null, "no_agency": null, "no_partnership": null, "survival": null, "further_assurance": null, "costs_and_expenses": null, "stamp_duty": null}},
  "code_of_conduct": {{"code_of_conduct": null, "customer_interaction_rules": null, "calling_restrictions": null, "communication_restrictions": null, "lead_generation_rules": null, "misrepresentation_prohibited": null, "false_promise_prohibited": null, "customer_consent": null, "data_collection_rules": null, "record_keeping": null, "follow_up_rules": null, "professional_conduct": null, "prohibited_practices": null}},
  "schedules": [{{"schedule_type": null, "schedule_number": "", "schedule_title": null, "schedule_content": null}}],
  "stamp": {{"stamp_present": null, "stamp_type": null, "stamp_value": null, "stamp_currency": "INR", "stamp_state": null, "stamp_serial_number": null, "stamp_issue_date": null, "stamp_authority": null, "notary_present": null, "notary_name": null, "notary_date": null, "notary_registration_number": null}},
  "signatures": {{"company_signatory": null, "service_provider_signatory": null, "witness_1_name": null, "witness_1_signature": null, "witness_2_name": null, "witness_2_signature": null, "rubber_stamp_present": null, "company_stamp_present": null, "service_provider_stamp_present": null, "stamp_text": null, "stamp_location": null}},
  "clause_metadata": [{{"clause_number": null, "clause_title": null, "page_number": null, "extraction_evidence": null}}],
  "document_metadata": {{"page_count": null, "total_clauses_detected": null, "extraction_notes": null}}
}}

OCR TEXT:
<<<OCR_TEXT>>>
{ocr_text}
<<<END_OCR_TEXT>>>
"""


# ---------------------------------------------------------------------------
# Extractor factory
# ---------------------------------------------------------------------------

class DocumentExtractor(ABC):
    document_type: str = "unknown"
    schema: Type[BaseModel]
    prompt_template: str

    def __init__(self, structured_extractor: StructuredExtractor):
        self.structured_extractor = structured_extractor

    def extract(self, ocr_text: str) -> BaseModel:
        prompt = self.build_prompt(ocr_text)
        return self.structured_extractor.extract(prompt=prompt, schema=self.schema)

    def build_prompt(self, ocr_text: str) -> str:
        return self.prompt_template.format(ocr_text=ocr_text)

    def post_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Optional regex-based fallback pass over the raw OCR text."""
        return result


class ExtractorFactory:
    _registry: Dict[str, Type[DocumentExtractor]] = {}

    @classmethod
    def register(cls, document_type: str):
        def decorator(extractor_cls: Type[DocumentExtractor]) -> Type[DocumentExtractor]:
            if not getattr(extractor_cls, "schema", None) or not getattr(extractor_cls, "prompt_template", None):
                raise TypeError(f"{extractor_cls.__name__} must define both 'schema' and 'prompt_template'")
            cls._registry[document_type.lower()] = extractor_cls
            return extractor_cls

        return decorator

    @classmethod
    def create(cls, document_type: str, structured_extractor: StructuredExtractor) -> DocumentExtractor:
        key = document_type.lower()
        if key not in cls._registry:
            raise ValueError(f"Unsupported document type: {document_type}. Available: {list(cls._registry)}")
        return cls._registry[key](structured_extractor)

    @classmethod
    def available_types(cls) -> list:
        return list(cls._registry)


@ExtractorFactory.register("aadhaar")
class AadhaarExtractor(DocumentExtractor):
    document_type = "aadhaar"
    schema = AadhaarDocument
    prompt_template = AADHAAR_EXTRACTION_PROMPT

    AADHAAR_PATTERNS = [
        r"(?:Your Aadhaar No\.)\s*:?\s*([\dXx\s]{12,17})",
        r"Aadhaar\s*No\.?\s*:?\s*([\dXx\s]{12,17})",
    ]
    TWELVE_DIGIT = re.compile(r"\b(\d{4}\s*\d{4}\s*\d{4})\b")
    ENROLMENT = re.compile(r"Enrolment No\.?\s*:?\s*([\d/]+)", re.IGNORECASE)
    VID = re.compile(r"VID\s*:?\s*(\d+)", re.IGNORECASE)
    DOB = re.compile(r"DOB\s*:?\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
    GUARDIAN = re.compile(r"(S/O|D/O|W/O|C/O)\s*:?\s*([A-Za-z\s]+?)(?:\n|$)", re.IGNORECASE)
    PINCODE = re.compile(r"\b(\d{6})\b")

    def post_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        data, ocr_text = result["data"], result["ocr_text"]

        if not data.get("aadhaar_number_masked") and not data.get("aadhaar_number_unmasked"):
            for pattern in self.AADHAAR_PATTERNS:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if not match:
                    continue
                candidate = re.sub(r"\s+", " ", match.group(1).strip())
                if "x" in candidate.lower():
                    data["aadhaar_number_masked"] = re.sub(r"x", "X", candidate, flags=re.IGNORECASE)
                    digits_match = self.TWELVE_DIGIT.search(ocr_text)
                    if digits_match:
                        data["aadhaar_number_unmasked"] = digits_match.group(1).replace(" ", "")
                else:
                    digits = re.sub(r"\D", "", candidate)
                    if len(digits) == 12:
                        data["aadhaar_number_unmasked"] = digits
                        data["aadhaar_number_masked"] = f"xxxx xxxx {digits[-4:]}"
                break

        if not data.get("enrolment_number"):
            match = self.ENROLMENT.search(ocr_text)
            if match:
                data["enrolment_number"] = match.group(1).strip()

        if not data.get("vid"):
            match = self.VID.search(ocr_text)
            if match:
                data["vid"] = match.group(1).strip()

        if not data.get("date_of_birth"):
            match = self.DOB.search(ocr_text)
            if match:
                data["date_of_birth"] = match.group(1).strip()

        if not data.get("guardian_name"):
            match = self.GUARDIAN.search(ocr_text)
            if match:
                data["guardian_name"] = f"{match.group(1).upper()}: {match.group(2).strip()}"

        if not data.get("pincode"):
            match = self.PINCODE.search(ocr_text)
            if match:
                data["pincode"] = match.group(1)

        result["data"] = data
        return result


@ExtractorFactory.register("pan")
class PANExtractor(DocumentExtractor):
    document_type = "pan"
    schema = PANDocument
    prompt_template = PAN_EXTRACTION_PROMPT

    PAN_NUMBER = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
    DOB = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")

    def post_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        data, ocr_text = result["data"], result["ocr_text"]

        if not data.get("pan_number"):
            match = self.PAN_NUMBER.search(ocr_text.upper())
            if match:
                data["pan_number"] = match.group(1)

        if not data.get("date_of_birth"):
            match = self.DOB.search(ocr_text)
            if match:
                data["date_of_birth"] = match.group(1)

        result["data"] = data
        return result


@ExtractorFactory.register("agreement")
class AgreementExtractor(DocumentExtractor):
    document_type = "agreement"
    schema = AgreementDocument
    prompt_template = AGREEMENT_EXTRACTION_PROMPT

    DATE = re.compile(r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})\b")
    STAMP_DUTY = re.compile(r"Stamp\s*Duty\D{0,10}(Rs\.?\s*[\d,]+)", re.IGNORECASE)
    PAN_NUMBER = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
    GSTIN = re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d])\b")
    IFSC = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")
    CIN = re.compile(r"\b([LUu]\d{5}[A-Za-z]{2}\d{4}[A-Za-z]{3}\d{6})\b")

    def build_prompt(self, ocr_text: str) -> str:
        return self.prompt_template.format(
            ocr_text=ocr_text,
            date_types=", ".join(DATE_TYPES),
            money_types=", ".join(MONEY_TYPES),
        )

    def post_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        data, ocr_text = result["data"], result["ocr_text"]
        upper_text = ocr_text.upper()

        # -- regex fallbacks for high-value structured identifiers -----------
        company = data.setdefault("company", {})
        if not company.get("pan"):
            match = self.PAN_NUMBER.search(upper_text)
            if match:
                company["pan"] = match.group(1)
        if not company.get("gstin"):
            match = self.GSTIN.search(upper_text)
            if match:
                company["gstin"] = match.group(1)

        service_provider = data.setdefault("service_provider", {})
        if not service_provider.get("pan"):
            match = self.PAN_NUMBER.search(upper_text)
            if match:
                service_provider["pan"] = match.group(1)

        payment_terms = data.setdefault("payment_terms", {})
        if not payment_terms.get("ifsc"):
            match = self.IFSC.search(upper_text)
            if match:
                payment_terms["ifsc"] = match.group(1)

        company_entity = (data.get("service_provider") or {}).get("company") or {}
        if not company_entity.get("cin"):
            match = self.CIN.search(upper_text)
            if match:
                company_entity["cin"] = match.group(1)
                service_provider["company"] = company_entity

        # -- generic fallbacks for a top-level agreement date / stamp duty ---
        dates = data.setdefault("dates", [])
        if not dates:
            match = self.DATE.search(ocr_text)
            if match:
                dates.append({"date_type": "agreement_date", "date_value": None,
                               "date_text_original": match.group(1).strip()})

        monetary_values = data.setdefault("monetary_values", [])
        if not any(mv.get("amount_type") == "STAMP_DUTY" for mv in monetary_values):
            match = self.STAMP_DUTY.search(ocr_text)
            if match:
                monetary_values.append({
                    "amount_text": match.group(1).strip(),
                    "amount_type": "STAMP_DUTY",
                    "currency": "INR",
                })

        result["data"] = data
        return result


# ---------------------------------------------------------------------------
# Face extractor (plug and play) - YuNet, aligned crop
# ---------------------------------------------------------------------------

class FaceExtractor(ABC):
    @abstractmethod
    def extract(self, image_path: Union[str, Path], output_path: Union[str, Path]) -> Optional[str]:
        ...


class YuNetFaceExtractor(FaceExtractor):
    def __init__(self, config: FaceDetectorSettings = settings.face):
        self.config = config
        self.model_path = self._resolve_model()

    def _resolve_model(self) -> str:
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(repo_id=self.config.repo_id, filename=self.config.filename)
        if os.path.getsize(path) < 10_000:
            raise RuntimeError(f"YuNet model download incomplete or corrupted: {path}")
        if not hasattr(cv2, "FaceDetectorYN"):
            raise RuntimeError("OpenCV build missing FaceDetectorYN. Install opencv-contrib-python.")
        return path

    def extract(self, image_path: Union[str, Path], output_path: Union[str, Path]) -> Optional[str]:
        image = cv2.imread(str(image_path))
        if image is None:
            raise FileNotFoundError(f"Could not read image: {image_path}")

        img_h, img_w = image.shape[:2]
        detector = cv2.FaceDetectorYN.create(
            model=self.model_path,
            config="",
            input_size=(img_w, img_h),
            score_threshold=self.config.score_threshold,
            nms_threshold=self.config.nms_threshold,
            top_k=self.config.top_k,
        )
        detector.setInputSize((img_w, img_h))
        _, faces = detector.detect(image)

        if faces is None or len(faces) == 0:
            logger.warning("No face detected in %s", image_path)
            return None

        best_face = max(faces, key=lambda f: f[14])
        cropped = self._align_and_crop(image, best_face)
        if cropped is None or cropped.size == 0:
            return None

        cropped = cv2.resize(cropped, self.config.output_size)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), cropped)
        return str(output_path)

    def _align_and_crop(self, image: np.ndarray, face: np.ndarray) -> Optional[np.ndarray]:
        box = face[0:4].astype(int)
        landmarks = face[4:14]
        x, y, box_w, box_h = box
        x, y = max(0, x), max(0, y)
        if box_w <= 0 or box_h <= 0:
            return None

        right_eye, left_eye = np.array(landmarks[0:2]), np.array(landmarks[2:4])
        dy, dx = left_eye[1] - right_eye[1], left_eye[0] - right_eye[0]
        angle = np.degrees(np.arctan2(dy, dx))
        eyes_center = ((right_eye[0] + left_eye[0]) / 2.0, (right_eye[1] + left_eye[1]) / 2.0)

        rot_matrix = cv2.getRotationMatrix2D(eyes_center, angle, 1.0)
        rotated = cv2.warpAffine(image, rot_matrix, (image.shape[1], image.shape[0]), flags=cv2.INTER_CUBIC)

        corners = np.array([[x, y], [x + box_w, y], [x, y + box_h], [x + box_w, y + box_h]])
        corners_h = np.hstack([corners, np.ones((4, 1))])
        transformed = rot_matrix.dot(corners_h.T).T

        x1 = max(0, int(np.min(transformed[:, 0])))
        y1 = max(0, int(np.min(transformed[:, 1])))
        x2 = min(rotated.shape[1], int(np.max(transformed[:, 0])))
        y2 = min(rotated.shape[0], int(np.max(transformed[:, 1])))

        padding = int(self.config.padding_ratio * max(x2 - x1, y2 - y1))
        x1, y1 = max(0, x1 - padding), max(0, y1 - padding)
        x2 = min(rotated.shape[1], x2 + padding)
        y2 = min(rotated.shape[0], y2 + padding)

        return rotated[y1:y2, x1:x2]


class HaarFaceExtractor(FaceExtractor):
    """Offline fallback - bundled with opencv-python, no model download required."""

    def __init__(self, padding_ratio: float = 0.35, output_size: Tuple[int, int] = (400, 400)):
        self.padding_ratio = padding_ratio
        self.output_size = output_size
        xml_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        self.cascade = cv2.CascadeClassifier(str(xml_path))
        if self.cascade.empty():
            raise RuntimeError("Failed to load bundled Haar cascade.")

    def extract(self, image_path: Union[str, Path], output_path: Union[str, Path]) -> Optional[str]:
        image = cv2.imread(str(image_path))
        if image is None:
            raise FileNotFoundError(f"Could not read image: {image_path}")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self.cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        if len(faces) == 0:
            logger.warning("No face detected in %s", image_path)
            return None

        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        pad_x, pad_y = int(w * self.padding_ratio), int(h * self.padding_ratio)
        img_h, img_w = image.shape[:2]
        x0, y0 = max(0, x - pad_x), max(0, y - pad_y)
        x1, y1 = min(img_w, x + w + pad_x), min(img_h, y + h + pad_y)
        cropped = image[y0:y1, x0:x1]

        if cropped.size == 0:
            return None

        cropped = cv2.resize(cropped, self.output_size, interpolation=cv2.INTER_CUBIC)
        blurred = cv2.GaussianBlur(cropped, (0, 0), 3)
        cropped = cv2.addWeighted(cropped, 1.5, blurred, -0.5, 0)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), cropped, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return str(output_path)


# ---------------------------------------------------------------------------
# QR extractor
# ---------------------------------------------------------------------------

class QRCodeExtractor:
    def __init__(self):
        self.detector = cv2.QRCodeDetector()

    def extract(self, image_path: Union[str, Path]) -> Optional[str]:
        image = cv2.imread(str(image_path))
        if image is None:
            return None
        try:
            data, _, _ = self.detector.detectAndDecode(image)
            return data or None
        except cv2.error:
            return None


# ---------------------------------------------------------------------------
# File type detection (images vs PDFs)
# ---------------------------------------------------------------------------

class FileKind(str, Enum):
    IMAGE = "image"
    PDF = "pdf"
    UNSUPPORTED = "unsupported"


class FileTypeDetector:
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".gif"}
    PDF_EXTENSIONS = {".pdf"}

    @classmethod
    def detect(cls, path: Union[str, Path]) -> FileKind:
        ext = Path(path).suffix.lower()
        if ext in cls.IMAGE_EXTENSIONS:
            return FileKind.IMAGE
        if ext in cls.PDF_EXTENSIONS:
            return FileKind.PDF
        return FileKind.UNSUPPORTED


class ImageNormalizer:
    """Makes sure any accepted image format can actually be read by cv2 for the
    face/QR steps. Most formats (png/jpg/bmp/tiff) work directly; a handful of
    builds struggle with webp/gif, so those get re-saved as PNG via PIL first."""

    @staticmethod
    def ensure_cv2_readable(image_path: Union[str, Path]) -> Path:
        image_path = Path(image_path)
        if cv2.imread(str(image_path)) is not None:
            return image_path

        pil_image = Image.open(image_path)
        if getattr(pil_image, "is_animated", False):
            pil_image.seek(0)  # first frame only, for animated GIFs
        pil_image = pil_image.convert("RGB")

        normalized_path = image_path.with_name(f"{image_path.stem}__normalized.png")
        pil_image.save(normalized_path)
        return normalized_path


# ---------------------------------------------------------------------------
# PDF -> page images
# ---------------------------------------------------------------------------

class PDFPageConverter:
    """Rasterizes every page of a PDF into a temporary PNG image using PyMuPDF."""

    def __init__(self, dpi: int = settings.pdf.dpi):
        self.dpi = dpi

    def convert(self, pdf_path: Union[str, Path], output_dir: Union[str, Path]) -> List[Path]:
        try:
            import fitz  # PyMuPDF
        except ImportError as e:
            raise ImportError(
                "PDF support requires the 'PyMuPDF' package (it provides the 'fitz' module). "
                "Installing a package literally named 'fitz' from PyPI is a DIFFERENT, unrelated, "
                "broken package and will fail to build. Run: pip install PyMuPDF"
            ) from e

        pdf_path = Path(pdf_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        zoom = self.dpi / 72
        matrix = fitz.Matrix(zoom, zoom)

        page_paths: List[Path] = []
        with fitz.open(pdf_path) as doc:
            if doc.page_count == 0:
                raise ValueError(f"PDF has no pages: {pdf_path}")
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=matrix)
                out_path = output_dir / f"{pdf_path.stem}_page{i + 1}.png"
                pix.save(str(out_path))
                page_paths.append(out_path)
        return page_paths


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class DocumentPipeline:
    def __init__(
        self,
        ocr: OCREngine,
        structured_extractor: StructuredExtractor,
        face_extractor: Optional[FaceExtractor] = None,
        qr_extractor: Optional[QRCodeExtractor] = None,
        pdf_converter: Optional[PDFPageConverter] = None,
    ):
        self.ocr = ocr
        self.structured_extractor = structured_extractor
        self.face_extractor = face_extractor or YuNetFaceExtractor()
        self.qr_extractor = qr_extractor or QRCodeExtractor()
        self.pdf_converter = pdf_converter or PDFPageConverter()

    def process(
        self,
        document_path: Union[str, Path],
        document_type: str,
        extract_face: bool = False,
        face_output_dir: Union[str, Path] = "extracted_faces",
    ) -> Dict[str, Any]:
        document_path = Path(document_path)
        if not document_path.exists():
            raise FileNotFoundError(f"Document not found: {document_path}")

        kind = FileTypeDetector.detect(document_path)
        if kind == FileKind.IMAGE:
            return self._process_image(document_path, document_type, extract_face, face_output_dir)
        if kind == FileKind.PDF:
            return self._process_pdf(document_path, document_type, extract_face, face_output_dir)
        raise ValueError(
            f"Unsupported file type '{document_path.suffix}' for {document_path}. "
            f"Supported: images {sorted(FileTypeDetector.IMAGE_EXTENSIONS)} or .pdf"
        )

    # -- image path -----------------------------------------------------

    def _process_image(
        self, document_path: Path, document_type: str, extract_face: bool, face_output_dir: Union[str, Path]
    ) -> Dict[str, Any]:
        readable_path = ImageNormalizer.ensure_cv2_readable(document_path)
        try:
            return self._run_pages([readable_path], document_type, document_path, extract_face, face_output_dir)
        finally:
            if readable_path != document_path:
                readable_path.unlink(missing_ok=True)

    # -- pdf path (multi-page, combined) ---------------------------------

    def _process_pdf(
        self, document_path: Path, document_type: str, extract_face: bool, face_output_dir: Union[str, Path]
    ) -> Dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="pdf_pages_") as temp_dir:
            page_paths = self.pdf_converter.convert(document_path, temp_dir)
            try:
                return self._run_pages(page_paths, document_type, document_path, extract_face, face_output_dir)
            finally:
                for page_path in page_paths:
                    page_path.unlink(missing_ok=True)
                logger.info("Deleted %d temp page image(s) for %s", len(page_paths), document_path.name)
        # TemporaryDirectory context manager removes the folder itself on exit too.

    # -- shared core: OCR every page, combine, extract once ---------------

    def _run_pages(
        self,
        image_paths: List[Path],
        document_type: str,
        source_path: Path,
        extract_face: bool,
        face_output_dir: Union[str, Path],
    ) -> Dict[str, Any]:
        label = document_type.replace("_", " ").title()
        logger.info("[%s] Processing: %s (%d page(s))", label, source_path.name, len(image_paths))

        page_texts = []
        for idx, img_path in enumerate(image_paths, start=1):
            logger.info("[%s] Running OCR on page %d/%d...", label, idx, len(image_paths))
            page_texts.append(self.ocr.extract_text(img_path))
        ocr_text = "\n----- PAGE BREAK -----\n".join(page_texts)

        logger.info("[%s] Extracting structured fields...", label)
        extractor = ExtractorFactory.create(document_type, self.structured_extractor)
        parsed = extractor.extract(ocr_text)

        result: Dict[str, Any] = {
            "document_type": document_type,
            "source_file": str(source_path),
            "page_count": len(image_paths),
            "ocr_text": ocr_text,
            "data": parsed.model_dump(),
        }

        logger.info("[%s] Scanning for QR code...", label)
        qr_data = None
        for img_path in image_paths:
            qr_data = self.qr_extractor.extract(img_path)
            if qr_data:
                break
        if qr_data:
            result["data"]["barcode_qr_raw_data"] = qr_data
            result["data"]["barcode_qr_code"] = "detected"

        result = extractor.post_process(result)

        if extract_face:
            logger.info("[%s] Extracting face photo...", label)
            for img_path in image_paths:
                out_path = Path(face_output_dir) / f"{source_path.stem}_face.jpg"
                face_path = self.face_extractor.extract(img_path, out_path)
                if face_path:
                    result["data"]["photo_path"] = face_path
                    break

        # re-validate after regex post-processing so bad values never leak out
        result["data"] = extractor.schema.model_validate(result["data"]).model_dump()
        logger.info("[%s] Processing complete.", label)
        return result


# ---------------------------------------------------------------------------
# Folder -> document type resolution + batch processing
# ---------------------------------------------------------------------------

class FolderDocumentTypeResolver:
    """
    Maps a folder name to a registered document_type - tolerant of case and
    common spelling variants/typos, so 'aadhar', 'AAdhar', 'Adhar', 'ADHAAR',
    'PAN', 'pan', 'pann', 'agreement', 'Agreements', 'aggrements' etc. all
    resolve correctly without listing every variant by hand.
    """

    DEFAULT_KEYWORDS: Dict[str, List[str]] = {
        "aadhaar": ["aadhaar", "aadhar", "adhaar", "adhar", "aadharcard", "uidai"],
        "pan": ["pan", "pancard", "pannumber"],
        "agreement": ["agreement", "agreements", "aggrement", "aggrements", "agrement", "contract", "deed"],
    }

    FUZZY_MATCH_CUTOFF = 0.72  # 0..1, higher = stricter typo tolerance

    def __init__(self, keywords: Optional[Dict[str, List[str]]] = None):
        self.keywords = {
            document_type: [kw.lower() for kw in kw_list]
            for document_type, kw_list in (keywords or self.DEFAULT_KEYWORDS).items()
        }

    @staticmethod
    def _normalize(name: str) -> str:
        return re.sub(r"[^a-z]", "", name.strip().lower())

    def resolve(self, folder_name: str) -> Optional[str]:
        normalized = self._normalize(folder_name)
        if not normalized:
            return None

        # 1) exact match, or the folder name IS one of the keywords with a trailing
        #    's' (simple pluralisation) - deliberately NOT a loose substring check,
        #    since e.g. "japan" must never match the "pan" keyword.
        for document_type, kw_list in self.keywords.items():
            for keyword in kw_list:
                if normalized == keyword or normalized == f"{keyword}s":
                    return document_type

        # 2) fuzzy match to catch typos like "pann" or "aggrements"
        best_type, best_score = None, 0.0
        for document_type, kw_list in self.keywords.items():
            for keyword in kw_list:
                score = difflib.SequenceMatcher(None, normalized, keyword).ratio()
                if score > best_score:
                    best_type, best_score = document_type, score

        return best_type if best_score >= self.FUZZY_MATCH_CUTOFF else None


@dataclass
class BatchResult:
    processed: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"processed={len(self.processed)}, "
            f"failed={len(self.failed)}, "
            f"skipped={len(self.skipped)}"
        )


class BatchFolderProcessor:
    """
    Walks a root folder whose sub-folders are named after document types
    (e.g. document/aadhar, document/pan, document/agreements) and processes
    every image or PDF found inside each one, auto-detecting file type.
    """

    def __init__(
        self,
        pipeline: DocumentPipeline,
        type_resolver: Optional[FolderDocumentTypeResolver] = None,
        output_dir: Union[str, Path] = "extracted_json",
        face_output_dir: Union[str, Path] = "extracted_faces",
        extract_face: bool = True,
    ):
        self.pipeline = pipeline
        self.type_resolver = type_resolver or FolderDocumentTypeResolver()
        self.output_dir = Path(output_dir)
        self.face_output_dir = Path(face_output_dir)
        self.extract_face = extract_face

    def run(self, root_folder: Union[str, Path]) -> BatchResult:
        root_folder = Path(root_folder)
        if not root_folder.is_dir():
            raise NotADirectoryError(f"Not a folder: {root_folder}")

        batch_result = BatchResult()

        for subfolder in sorted(p for p in root_folder.iterdir() if p.is_dir()):
            document_type = self.type_resolver.resolve(subfolder.name)
            if document_type is None:
                logger.warning("Skipping unrecognised folder: %s", subfolder.name)
                batch_result.skipped.append(str(subfolder))
                continue

            for file_path in sorted(p for p in subfolder.iterdir() if p.is_file()):
                kind = FileTypeDetector.detect(file_path)
                if kind == FileKind.UNSUPPORTED:
                    logger.warning("Skipping unsupported file: %s", file_path)
                    batch_result.skipped.append(str(file_path))
                    continue

                try:
                    result = self.pipeline.process(
                        document_path=file_path,
                        document_type=document_type,
                        extract_face=self.extract_face,
                        face_output_dir=self.face_output_dir,
                    )
                    json_path = self._save_result(file_path, subfolder.name, result)
                    batch_result.processed.append(str(json_path))
                except Exception:
                    logger.exception("Failed to process %s", file_path)
                    batch_result.failed.append(str(file_path))

        logger.info("Batch complete: %s", batch_result.summary())
        return batch_result

    def _save_result(self, file_path: Path, subfolder_name: str, result: Dict[str, Any]) -> Path:
        out_dir = self.output_dir / subfolder_name
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = out_dir / f"{file_path.stem}.json"
        save_json(result, str(json_path))
        return json_path


# ---------------------------------------------------------------------------
# Helpers / entrypoint
# ---------------------------------------------------------------------------

def save_json(data: Dict[str, Any], output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def build_pipeline() -> DocumentPipeline:
    ocr = GLMOCR()
    structured_extractor = GLMStructuredExtractor(ocr=ocr)
    return DocumentPipeline(ocr=ocr, structured_extractor=structured_extractor)


def main():
    """
    Point ROOT_FOLDER at a directory laid out like:

        document/
          aadhar/       -> images and/or PDFs of Aadhaar cards
          pan/           -> images and/or PDFs of PAN cards
          agreements/    -> images and/or (often multi-page) PDFs of agreements

    Every file's type (image vs PDF) and its document type (from the folder
    name) are auto-detected. Results land in extracted_json/<folder>/<file>.json,
    faces in extracted_faces/, and any temp PDF-page images are deleted right
    after each file is processed.
    """
    ROOT_FOLDER = "Documents"

    pipeline = build_pipeline()
    processor = BatchFolderProcessor(pipeline=pipeline)
    result = processor.run(ROOT_FOLDER)

    logger.info("Processed files:")
    for path in result.processed:
        logger.info("  OK   %s", path)
    for path in result.failed:
        logger.info("  FAIL %s", path)
    for path in result.skipped:
        logger.info("  SKIP %s", path)


if __name__ == "__main__":
    main()
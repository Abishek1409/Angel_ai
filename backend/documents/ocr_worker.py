"""
Standalone OCR process for scanned PDF pages.

Run as:  python ocr_worker.py <pdf_path> <page_index> [<page_index> ...]
Prints one line "<RESULT_MARKER>{"<page_index>": "<text>", ...}" to stdout;
library logging goes to stderr.

OCR runs in its own short-lived process (not inside the web worker) so the
OCR model's memory (~150-200 MB) is returned to the OS as soon as the
document is done. This keeps the web service under small memory limits.
It deliberately imports nothing from Django.
"""
import json
import shutil
import sys

import fitz  # PyMuPDF
import numpy as np

RESULT_MARKER = "__OCR_RESULT__"
OCR_DPI = 200
MAX_SIDE_PX = 2000  # cap very large pages to bound memory

# Tuned for a 512 MB host: measured peak ~260 MB (vs ~520 MB with defaults)
# on a dense full page, with no loss of accuracy on upright scans.
ENGINE_PARAMS = {
    "Global.use_cls": False,          # skip the text-angle model; scans are upright
    "Det.limit_type": "max",          # downscale for detection instead of upscaling
    "Det.limit_side_len": 960,
    "Rec.rec_batch_num": 1,           # recognise one line at a time: biggest memory saver
    "EngineConfig.onnxruntime.intra_op_num_threads": 2,
    "EngineConfig.onnxruntime.inter_op_num_threads": 1,
}

_engine = None


def _render_page(page) -> np.ndarray:
    zoom = OCR_DPI / 72
    longest = max(page.rect.width, page.rect.height) * zoom
    if longest > MAX_SIDE_PX:
        zoom *= MAX_SIDE_PX / longest
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csRGB, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()


def _rapidocr(image) -> str:
    global _engine
    if _engine is None:
        from rapidocr import RapidOCR

        _engine = RapidOCR(params=ENGINE_PARAMS)
    result = _engine(image)
    return "\n".join(result.txts or ())


def _tesseract(image) -> str:
    if not shutil.which("tesseract"):
        raise RuntimeError("tesseract is not installed")
    import pytesseract
    from PIL import Image

    return pytesseract.image_to_string(Image.fromarray(image))


def ocr_page(page) -> str:
    image = _render_page(page)
    try:
        return _rapidocr(image)
    except Exception as e:
        print(f"RapidOCR failed ({e}); trying Tesseract", file=sys.stderr)
    return _tesseract(image)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: ocr_worker.py <pdf_path> <page_index> ...", file=sys.stderr)
        return 2
    path, indexes = argv[0], [int(i) for i in argv[1:]]
    # Libraries may log to stdout; keep it clean for the result line
    result_stream, sys.stdout = sys.stdout, sys.stderr
    results = {}
    with fitz.open(path) as doc:
        for index in indexes:
            results[str(index)] = ocr_page(doc[index])
    result_stream.write("\n" + RESULT_MARKER + json.dumps(results) + "\n")
    result_stream.flush()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:  # report the reason to the parent process
        print(f"OCR failed: {e}", file=sys.stderr)
        sys.exit(1)

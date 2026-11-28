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
import os
import shutil
import sys

import fitz  # PyMuPDF
import numpy as np

RESULT_MARKER = "__OCR_RESULT__"
OCR_DPI = 200
MAX_SIDE_PX = 1600  # cap very large pages to bound memory

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr_models")
DET_MODEL = os.path.join(MODELS_DIR, "en_PP-OCRv3_det_mobile.onnx")
REC_MODEL = os.path.join(MODELS_DIR, "en_PP-OCRv4_rec_mobile.onnx")

# Tuned for a 512 MB host. Measured on Linux (python:3.11-slim) on a dense
# full page: ~260 MB peak with these settings vs ~520 MB with rapidocr's
# defaults, at the same accuracy on upright scans.
BASE_PARAMS = {
    "Global.use_cls": False,          # skip the text-angle model; scans are upright
    "Det.limit_type": "max",          # downscale for detection instead of upscaling
    "Det.limit_side_len": 960,
    "Rec.rec_batch_num": 1,           # recognise one line at a time: big memory saver
    "EngineConfig.onnxruntime.intra_op_num_threads": 2,
    "EngineConfig.onnxruntime.inter_op_num_threads": 1,
}

_engine = None


def engine_params() -> dict:
    """Use the small English mobile models kept in the repo; fall back to rapidocr's bundled ones."""
    params = dict(BASE_PARAMS)
    if os.path.exists(DET_MODEL) and os.path.exists(REC_MODEL):
        from rapidocr import LangDet, LangRec, ModelType, OCRVersion

        params.update({
            "Det.ocr_version": OCRVersion.PPOCRV4,
            "Det.lang_type": LangDet.EN,
            "Det.model_type": ModelType.MOBILE,
            "Det.model_path": DET_MODEL,
            "Rec.ocr_version": OCRVersion.PPOCRV4,
            "Rec.lang_type": LangRec.EN,
            "Rec.model_type": ModelType.MOBILE,
            "Rec.model_path": REC_MODEL,
        })
    else:
        print("Repo OCR models missing; using rapidocr's bundled models", file=sys.stderr)
    return params


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

        _engine = RapidOCR(params=engine_params())
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

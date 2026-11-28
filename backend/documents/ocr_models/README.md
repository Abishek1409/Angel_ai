# OCR models

Lightweight PaddleOCR models (Apache License 2.0) in ONNX format, used by
`documents/ocr_worker.py` through RapidOCR. They are kept in the repo so the
server never has to download them after a restart.

| File | Purpose | Source |
| --- | --- | --- |
| `en_PP-OCRv3_det_mobile.onnx` | finds text lines on a page | RapidOCR v3.10.0 model zoo (`onnx/PP-OCRv4/det/`) |
| `en_PP-OCRv4_rec_mobile.onnx` | reads each line (English) | RapidOCR v3.10.0 model zoo (`onnx/PP-OCRv4/rec/`) |

On Linux these peak at ~260 MB per OCR run versus ~355 MB for the larger
PP-OCRv6 models bundled with the `rapidocr` package, which fit a 512 MB host.
If the files are missing, the worker falls back to the bundled models.

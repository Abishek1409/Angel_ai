"""
Standalone process for the offline embedding fallback (all-MiniLM-L6-v2 via ONNX).

Run as:  python embed_worker.py   with a JSON list of strings on stdin.
Prints one line "<RESULT_MARKER>[[...], ...]" to stdout; logging goes to stderr.

The model needs ~100 MB once loaded. Running it in a short-lived process,
instead of inside the web worker, returns that memory after every call so it
cannot stack with OCR on a 512 MB host. Only used when Gemini and the hosted
Hugging Face API both fail. It deliberately imports nothing from Django.
"""
import json
import sys

RESULT_MARKER = "__EMBED_RESULT__"
BATCH_SIZE = 4


def main() -> int:
    texts = json.loads(sys.stdin.read() or "[]")
    result_stream, sys.stdout = sys.stdout, sys.stderr  # keep stdout clean for the result
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    # Small batches: on Linux a batch of 12 chunks peaks at ~330 MB, batches of 4 at ~255 MB
    embed = DefaultEmbeddingFunction()
    vectors = []
    for i in range(0, len(texts), BATCH_SIZE):
        vectors.extend(embed(texts[i:i + BATCH_SIZE]))
    result_stream.write("\n" + RESULT_MARKER + json.dumps([[float(x) for x in v] for v in vectors]) + "\n")
    result_stream.flush()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # report the reason to the parent process
        print(f"Embedding failed: {e}", file=sys.stderr)
        sys.exit(1)

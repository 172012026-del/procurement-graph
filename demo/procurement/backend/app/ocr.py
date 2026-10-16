"""Bounded, local Chinese OCR with table-row reconstruction."""
from __future__ import annotations

import importlib.util
import shutil
import threading

from PIL import Image

_engine = None
_lock = threading.Lock()


def available() -> bool:
    return bool(shutil.which('tesseract') or importlib.util.find_spec('rapidocr'))


def image_text(image: Image.Image) -> str:
    if shutil.which('tesseract'):
        import pytesseract
        return pytesseract.image_to_string(image, lang='chi_sim+eng', timeout=60)
    global _engine
    with _lock:
        if _engine is None:
            from rapidocr import RapidOCR
            _engine = RapidOCR(params={'EngineConfig.onnxruntime.intra_op_num_threads': 2,
                'EngineConfig.onnxruntime.inter_op_num_threads': 1, 'Global.log_level': 'warning'})
        output = _engine(image)
        texts = output.txts or []
        boxes = output.boxes
        if boxes is None:
            return '\n'.join(texts)
        cells = []
        for text, box in zip(texts, boxes):
            xs, ys = [float(p[0]) for p in box], [float(p[1]) for p in box]
            cells.append((sum(ys)/len(ys), min(xs), max(ys)-min(ys), text))
        lines = []
        for y, x, height, text in sorted(cells):
            if not lines or abs(y-lines[-1]['y']) > max(5, min(height, lines[-1]['height'])*.55):
                lines.append({'y': y, 'height': height, 'cells': []})
            lines[-1]['cells'].append((x, text))
        return '\n'.join(' | '.join(text for _, text in sorted(line['cells'])) for line in lines)

"""Offline BM25 retrieval of curated domain rules; never indexes reference answers."""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re

KNOWLEDGE = Path(__file__).parent / 'knowledge/procurement.json'


def tokens(text: str) -> list[str]:
    words = re.findall(r'[a-z0-9]+', text.lower())
    for segment in re.findall(r'[\u4e00-\u9fff]+', text):
        words.extend(segment[index:index + 2] for index in range(max(1, len(segment) - 1)))
    return words


@lru_cache(maxsize=1)
def documents() -> tuple[dict, ...]:
    return tuple(json.loads(KNOWLEDGE.read_text('utf-8')))


def retrieve(query: str, top_k: int = 3, max_chars: int = 1800) -> list[dict]:
    corpus = documents()
    counts = [Counter(tokens(row['title'] + row['text'] + row['keywords'])) for row in corpus]
    lengths = [sum(row.values()) for row in counts]
    average = sum(lengths) / max(1, len(lengths))
    scores = []
    for index, counts_row in enumerate(counts):
        score = 0.0
        for term in set(tokens(query)):
            frequency = counts_row[term]
            if not frequency:
                continue
            document_frequency = sum(term in candidate for candidate in counts)
            weight = math.log(1 + (len(corpus) - document_frequency + .5) / (document_frequency + .5))
            score += weight * frequency * 2.2 / (frequency + 1.2 * (.25 + .75 * lengths[index] / average))
        if score:
            scores.append((score, index))
    output, used = [], 0
    for score, index in sorted(scores, key=lambda row: (-row[0], row[1]))[:max(0, min(top_k, 6))]:
        document = corpus[index]
        cost = len(document['title']) + len(document['text']) + len(document['id']) + 16
        if used + cost > max_chars:
            continue
        output.append({'id': document['id'], 'title': document['title'], 'text': document['text'], 'score': round(score, 5)})
        used += cost
    return output


def augment(text: str) -> tuple[str, list[str], str]:
    selected = retrieve(text)
    if not selected:
        return text, [], ''
    knowledge = '\n'.join(f"[{row['id']}] {row['title']}：{row['text']}" for row in selected)
    fingerprint = hashlib.sha256(knowledge.encode()).hexdigest()
    context = '[领域参考，仅解释提取规则，不是当前公告事实，不得用作字段证据]\n' + knowledge
    return context + '\n[待抽取文档]\n' + text, [row['id'] for row in selected], fingerprint

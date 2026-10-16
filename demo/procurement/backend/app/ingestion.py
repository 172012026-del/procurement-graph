from __future__ import annotations

import hashlib
import re
from pathlib import Path

from bs4 import BeautifulSoup

from .config import settings
from .parsers import ArchiveBudget, NOTICE_ID, ParseError, decode_text, detect_type, group_documents, safe_unzip


def discover_uploads(paths: list[Path], workdir: Path, issues: list[str]) -> list[list[Path]]:
    """Unpack batch containers but retain each UUID attachment ZIP for lazy processing."""
    queue = [(path, 0) for path in paths]
    leaves = []
    budget = ArchiveBudget()
    archive_index = 0
    while queue:
        path, depth = queue.pop(0)
        try:
            kind = detect_type(path)
            if kind == '.zip' and not NOTICE_ID.fullmatch(path.stem):
                archive_index += 1
                if depth > 8 or archive_index > 2000:
                    raise ParseError('批量压缩包层级或数量超限')
                children = safe_unzip(path, workdir / f'batch_{archive_index}', budget=budget)
                queue.extend((child, depth + 1) for child in children)
            else:
                leaves.append(path)
        except Exception as exc:
            issues.append(f'{path.name}: {type(exc).__name__}: {exc}')
    htmls = [p for p in leaves if p.suffix.lower() in {'.html', '.htm'}]
    if len({p.stem for p in htmls}) != len(htmls):
        raise ParseError('上传数据中有重名公告，请分开导入不同版本')
    if not htmls:
        return group_documents(leaves)
    grouped = {p: [p] for p in sorted(htmls, key=str)}
    for path in (p for p in leaves if p not in htmls):
        candidates = [h for h in htmls if h.stem == path.stem or h.stem in path.parts]
        if not candidates and len(htmls) == 1:
            candidates = htmls
        if len(candidates) == 1:
            grouped[candidates[0]].append(path)
        else:
            issues.append(f'附件未归属，未自动猜测: {path.name}')
    return list(grouped.values())


def local_groups(limit: int | None = None, notice_ids: list[str] | None = None) -> list[list[Path]]:
    root = settings.official_data_dir
    html_dir, file_dir = root / 'html', root / 'file'
    if not html_dir.is_dir():
        raise ValueError('未配置可读取的官方数据目录')
    requested = set(notice_ids or [])
    if any(not NOTICE_ID.fullmatch(name) for name in requested):
        raise ValueError('公告标识格式不正确')
    htmls = sorted(html_dir.glob('*.html'))
    if requested:
        available = {p.stem for p in htmls}
        if requested - available:
            raise ValueError('部分公告标识不存在')
        htmls = [p for p in htmls if p.stem in requested]
    groups = []
    for notice in htmls[:limit] if limit else htmls:
        if not notice.resolve().is_relative_to(root.resolve()):
            raise ValueError('公告路径越界')
        attachment = file_dir / f'{notice.stem}.zip'
        if attachment.exists() and not attachment.resolve().is_relative_to(root.resolve()):
            raise ValueError('附件路径越界')
        groups.append([notice, attachment] if attachment.is_file() else [notice])
    return groups


def input_digest(paths: list[Path], pipeline: str) -> str:
    result = hashlib.sha256(pipeline.encode())
    for path in sorted(paths, key=lambda x: x.name):
        result.update(path.name.encode('utf-8'))
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024**2), b''):
                result.update(chunk)
    return result.hexdigest()


def notice_metadata(path: Path) -> dict:
    if path.suffix.lower() not in {'.html', '.htm'}:
        return {'notice_uuid': path.stem}
    soup = BeautifulSoup(decode_text(path.read_bytes()), 'lxml')
    meta = {tag.get('name'): tag.get('content', '') for tag in soup.find_all('meta') if tag.get('name')}
    canonical = soup.find('link', rel='canonical')
    source = canonical.get('href', '') if canonical else ''
    provenance = 'canonical' if source else ''
    # The downloaded copies omit their own URL. Preserve how a candidate URL was obtained.
    if not source and meta.get('SiteDomain') == 'www.ccgp.gov.cn' and NOTICE_ID.fullmatch(path.stem):
        labels = [a.get_text(strip=True) for a in soup.find_all('a')]
        area = 'zygg' if '中央公告' in labels else 'dfgg' if '地方公告' in labels else ''
        kinds = {'中标公告': 'zbgg', '成交公告': 'cjgg', '公开招标公告': 'gkzb', '更正公告': 'gzgg'}
        kind = next((value for label, value in kinds.items() if label in labels), '')
        if area and kind:
            source = f'https://www.ccgp.gov.cn/cggg/{area}/{kind}/{path.stem[1:7]}/{path.stem}.htm'
            provenance = 'reconstructed_from_ccgp_breadcrumb'
    return {'notice_uuid': path.stem, 'source_url': source,
            'project_name': meta.get('ArticleTitle', ''),
            'announcement_date': meta.get('PubDate', '').split(' ')[0],
            'url_provenance': provenance}

"""Fetch official portable parsing tools into this workspace (no system install)."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import httpx

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'tools/downloads'


def sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def download(client, url: str, target: Path, expected: str | None = None) -> dict:
    if not target.resolve().is_relative_to(DEST.resolve()):
        raise ValueError('Tool path escapes download directory')
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + '.part')
    if target.exists() and expected and sha256(target) == expected:
        return {'url': url, 'file': target.name, 'sha256': expected, 'bytes': target.stat().st_size}
    if target.exists() and not partial.exists():
        target.rename(partial)
    if partial.exists() and expected and sha256(partial) == expected:
        partial.replace(target)
        return {'url': url, 'file': target.name, 'sha256': expected, 'bytes': target.stat().st_size}
    for attempt in range(16):
        offset = partial.stat().st_size if partial.exists() and expected else 0
        try:
            with client.stream('GET', url, headers={'Range': f'bytes={offset}-'} if offset else {}) as response:
                response.raise_for_status()
                total = int(response.headers.get('content-range', '/0').rsplit('/', 1)[-1]) if response.status_code == 206 else int(response.headers.get('content-length', 0))
                if total > 1024**3:
                    raise ValueError('Tool archive is unexpectedly large')
                with partial.open('ab' if response.status_code == 206 else 'wb') as output:
                    for block in response.iter_bytes(1024*1024):
                        output.write(block)
                if total and partial.stat().st_size != total:
                    raise ValueError('Incomplete tool download')
            digest = sha256(partial)
            if expected and digest != expected:
                raise ValueError('Official SHA256 does not match tool download')
            partial.replace(target)
            return {'url': url, 'file': target.name, 'sha256': digest, 'bytes': target.stat().st_size}
        except (httpx.HTTPError, OSError) as exc:
            if isinstance(exc, httpx.HTTPStatusError) and 400 <= exc.response.status_code < 500 and exc.response.status_code != 429:
                raise
            print(json.dumps({'file': target.name, 'attempt': attempt+1,
                'downloaded_bytes': partial.stat().st_size if partial.exists() else 0,
                'retry': type(exc).__name__}), flush=True)
    raise RuntimeError('Could not complete verified tool download')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--direct', action='store_true', help='Use direct HTTPS when the local system proxy is unavailable')
    parser.add_argument('--office-version', default='26.8.1')
    parser.add_argument('--office-only', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+', args.office_version):
        parser.error('Invalid version')
    records = []
    with httpx.Client(trust_env=not args.direct, follow_redirects=True, timeout=60) as client:
        def fetch(url):
            for attempt in range(5):
                try:
                    response = client.get(url)
                    response.raise_for_status()
                    return response
                except httpx.TransportError:
                    if attempt == 4:
                        raise
        if not args.office_only:
            listing = fetch('https://www.7-zip.org/download.html')
            page = BeautifulSoup(listing.content, 'html.parser')
            links = [urljoin(str(listing.url), a['href']) for a in page.find_all('a', href=True)]
            for suffix, filename in [('/7zr.exe', '7zr.exe'), ('-x64.exe', '7zip-x64.exe')]:
                url = next(u for u in links if u.endswith(suffix))
                records.append(download(client, url, DEST/filename))
        base = f'https://download.documentfoundation.org/libreoffice/stable/{args.office_version}/win/x86_64/'
        listing = fetch(base)
        page = BeautifulSoup(listing.content, 'html.parser')
        url = next(urljoin(base, a['href']) for a in page.find_all('a', href=True) if a['href'].endswith('_x86-64.msi'))
        checksum = fetch(url + '.sha256')
        expected = re.search(r'\b[0-9a-fA-F]{64}\b', checksum.text).group().lower()
        records.append(download(client, url, DEST/'libreoffice-x64.msi', expected))
    (ROOT/'tools/tool-sources.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    print(json.dumps({'verified_downloads': records}), flush=True)


if __name__ == '__main__':
    main()

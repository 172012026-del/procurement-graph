"""Install official parsing tools into tools/ on Windows; no global installation."""
from __future__ import annotations

import argparse
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'demo/procurement/backend'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--direct', action='store_true')
    args = parser.parse_args()
    from app.parsers import office_tool, seven_zip
    if office_tool() and seven_zip():
        print('LibreOffice/legacy Office reader and 7-Zip are available.')
        return
    if os.name != 'nt':
        raise SystemExit('Use the supplied Dockerfile, or install: sudo apt-get install libreoffice-writer libreoffice-calc 7zip tesseract-ocr tesseract-ocr-chi-sim')
    command = [sys.executable, str(ROOT / 'scripts/download_local_tools.py')]
    if args.direct:
        command.append('--direct')
    subprocess.run(command, cwd=ROOT, check=True)
    downloads = ROOT / 'tools/downloads'
    if not seven_zip():
        destination = ROOT / 'tools/sevenzip'
        destination.mkdir(parents=True, exist_ok=True)
        subprocess.run([str(downloads / '7zr.exe'), 'x', '-y', '-o' + str(destination), str(downloads / '7zip-x64.exe')], cwd=ROOT, check=True)
        if not (destination / '7z.exe').is_file():
            raise RuntimeError('7-Zip extraction failed')
    if not office_tool():
        staging = ROOT / '.cache/tool-install'
        staging.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='office-', dir=staging) as temporary:
            target = Path(temporary).resolve()
            subprocess.run(['msiexec.exe', '/a', str(downloads / 'libreoffice-x64.msi'), '/qn',
                            'TARGETDIR=' + str(target), '/L*v', str(target / 'install.log')], cwd=ROOT, check=True)
            programs = list(target.rglob('soffice.com'))
            if len(programs) != 1:
                raise RuntimeError('Cannot locate the extracted LibreOffice runtime')
            shutil.copytree(programs[0].parent.parent, ROOT / 'tools/libreoffice', dirs_exist_ok=True)
    if not office_tool() or not seven_zip():
        raise RuntimeError('Native tool verification failed')
    print('Project-local parsing tools are ready.')


if __name__ == '__main__':
    main()

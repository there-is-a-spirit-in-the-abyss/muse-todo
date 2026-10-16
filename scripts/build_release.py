"""Package an explicit allowlist; never include databases, backups or credentials."""
import hashlib
import io
import json
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ('muse_todo', 'bin', 'scripts', 'tests', 'references', 'docs', 'evidence')
FILES = ('SKILL.md', 'README.md', 'MUSE_PROMPT.md', '.gitignore')


def main():
    files = [ROOT / name for name in FILES]
    for folder in FOLDERS:
        for p in (ROOT / folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py', '.md', '.json', '.txt'}:
                if p.is_symlink() or not p.resolve().is_relative_to(ROOT):
                    raise ValueError('refusing linked files')
                files.append(p)
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    manifest = json.dumps(dict(format=1, sha256=hashes), indent=2).encode('utf-8')
    dest = ROOT / 'dist'
    dest.mkdir(exist_ok=True)
    archive = dest / 'muse-todo-v1.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for path in sorted(files):
            tar.add(path, arcname='muse-todo/' + path.relative_to(ROOT).as_posix(), recursive=False)
        entry = tarfile.TarInfo('muse-todo/release-manifest.json')
        entry.size = len(manifest)
        entry.mode = 0o644
        tar.addfile(entry, io.BytesIO(manifest))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (dest / 'SHA256SUMS.txt').write_text(checksum + '  ' + archive.name + '\n', encoding='ascii')
    print(json.dumps(dict(archive=str(archive), files=len(files) + 1, sha256=checksum)))


if __name__ == '__main__':
    main()

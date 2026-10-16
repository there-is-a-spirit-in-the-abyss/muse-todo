"""Safely extract our release, verify hashes, and run its actual packaged tests."""
import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    archive = ROOT / 'dist/muse-todo-v1.tar.gz'
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp).resolve()
        with tarfile.open(archive, 'r:gz') as tar:
            for item in tar.getmembers():
                target = base / item.name
                if not target.resolve().is_relative_to(base) or not item.isfile():
                    raise ValueError('unsafe release member')
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(item) as stream:
                    target.write_bytes(stream.read())
        release = base / 'muse-todo'
        manifest = json.loads((release / 'release-manifest.json').read_text(encoding='utf-8'))
        for rel, expected in manifest['sha256'].items():
            path = release / rel
            if not path.resolve().is_relative_to(release) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError('release checksum mismatch: ' + rel)
        run = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                             cwd=release, capture_output=True, encoding='utf-8')
    evidence = ROOT / 'evidence/release-check.txt'
    evidence.write_text('Release member hashes: passed\n' + run.stdout + run.stderr, encoding='utf-8')
    print(json.dumps(dict(checksums='passed', packaged_tests_exit_code=run.returncode, evidence=str(evidence))))
    return run.returncode


if __name__ == '__main__':
    raise SystemExit(main())

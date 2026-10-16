"""Build public release assets from a committed Git revision; standard library only."""
import argparse
import hashlib
import io
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPO = 'openwrt-f50-plugins'
CAMPUS = False


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def build(version, output, revision='HEAD'):
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?', version):
        raise ValueError('Expected vMAJOR.MINOR.PATCH (optional prerelease suffix)')
    # Resolve before writing: archives always come from one immutable commit.
    commit = git('rev-parse', '--verify', revision + '^{commit}').decode().strip()
    output.mkdir(parents=True, exist_ok=True)
    names = []

    def archive(name, paths=()):
        prefix = name.removesuffix('.zip') + '/'
        blob = git('archive', '--format=zip', '--prefix=' + prefix, commit, *paths)
        # Integrity check before producing a downloadable asset.
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            if z.testzip() is not None:
                raise ValueError('Corrupt source archive')
        (output / name).write_bytes(blob)
        names.append(name)

    archive(f'{REPO}-{version}-source.zip')
    if CAMPUS:
        archive(f'{REPO}-{version}-scriptable.zip',
                ('scriptable', 'config.example.json', 'docs', 'tools/export-official-session.js',
                 'tools/make_bookmarklet.py', 'README.md', 'LICENSE', 'SECURITY.md', 'CHANGELOG.md'))
        name = f'campus-balance-{version}.js'
        content = git('show', f'{commit}:scriptable/校园余额.js')
        # Keep MIT and font license notices when sharing the single-file widget.
        for path in ('LICENSE', 'docs/licenses/doto-OFL.txt', 'docs/licenses/spacemono-OFL.txt'):
            notice = git('show', f'{commit}:{path}').decode()
            content += ('\n' + '\n'.join('// ' + line for line in notice.splitlines()) + '\n').encode()
        (output / name).write_bytes(content)
        names.append(name)
    else:
        common = ('README.md', 'LICENSE', 'SECURITY.md', 'CHANGELOG.md', 'docs')
        for component in ('f50-ra-refresh', 'f50-xiaojing'):
            archive(f'{component}-{version}-source.zip',
                    (component, 'luci-app-' + component, *common))
    checksums = ''.join(hashlib.sha256((output / name).read_bytes()).hexdigest()
                        + '  ' + name + '\n' for name in names)
    (output / 'SHA256SUMS.txt').write_text(checksums, encoding='utf-8')
    print(f'Commit: {commit}')
    for name in [*names, 'SHA256SUMS.txt']:
        print(output / name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    parser.add_argument('--revision', default='HEAD')
    args = parser.parse_args()
    build(args.version, args.output, args.revision)

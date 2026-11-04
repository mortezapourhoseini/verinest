"""Build the Windows app folder dist/VeriNest/ with PyInstaller and bundle Icarus Verilog.

usage (on Windows):  python packaging/windows/build.py [path\\to\\iverilog]
                     (default iverilog folder: C:\\iverilog)
Result: dist/VeriNest/VeriNest.exe  (+ dist/VeriNest/iverilog/bin, lib)
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.join(ROOT, 'packaging', 'windows')
IVERILOG = sys.argv[1] if len(sys.argv) > 1 else r'C:\iverilog'


def main():
    os.chdir(ROOT)
    sep = os.pathsep
    subprocess.check_call([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed',
        '--name', 'VeriNest',
        '--icon', os.path.join(HERE, 'verinest.ico'),
        '--add-data', 'web' + sep + 'web',
        '--add-data', 'examples' + sep + 'examples',
        '--paths', ROOT,
        '--collect-submodules', 'verinest',
        os.path.join(HERE, 'verinest_app.py'),
    ])
    app = os.path.join(ROOT, 'dist', 'VeriNest')
    # bundle Icarus Verilog (binaries + its lib/ivl modules)
    dst = os.path.join(app, 'iverilog')
    for sub in ('bin', 'lib'):
        src = os.path.join(IVERILOG, sub)
        if not os.path.isdir(src):
            sys.exit('Icarus Verilog folder not found: ' + src)
        shutil.copytree(src, os.path.join(dst, sub), dirs_exist_ok=True)
    # GTKWave is not needed: VeriNest has its own waveform viewer
    for junk in ('gtkwave.exe',):
        p = os.path.join(dst, 'bin', junk)
        if os.path.exists(p):
            os.remove(p)
    for f in ('README.md', 'README.fa.md', 'LICENSE', 'CHANGELOG.md'):
        shutil.copy(os.path.join(ROOT, f), app)
    with open(os.path.join(app, 'THIRD-PARTY.txt'), 'w', encoding='utf-8') as fh:
        fh.write('VeriNest bundles:\n'
                 '- Icarus Verilog (GPL-2.0), https://github.com/steveicarus/iverilog\n'
                 '  Windows build by bleyer.org; source code: https://github.com/steveicarus/iverilog\n'
                 '- Monaco Editor (MIT), see _internal/web/vendor/monaco/LICENSE\n'
                 '- Python runtime (PSF license), packaged with PyInstaller\n')
    print('built', app)


if __name__ == '__main__':
    main()

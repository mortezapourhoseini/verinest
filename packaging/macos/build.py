"""Build VeriNest.app (and VeriNest-<version>-macOS-<arch>.dmg) on macOS.

usage:  brew install icarus-verilog && pip install pyinstaller pywebview
        python packaging/macos/build.py

Icarus Verilog from Homebrew is copied into the bundle
(VeriNest.app/Contents/Resources/iverilog). Its non-system dylibs are copied
next to it and re-linked with @loader_path, so the app does not need Homebrew.
Everything is ad-hoc signed; the app is not notarised (see README).
"""
import os
import platform
import shutil
import stat
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.join(ROOT, 'packaging', 'macos')
sys.path.insert(0, ROOT)
from verinest import __version__  # noqa: E402

SYSTEM_PREFIXES = ('/usr/lib/', '/System/')


def sh(*cmd, capture=False):
    print('+', ' '.join(cmd), flush=True)
    if capture:
        return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    subprocess.check_call(cmd)


def is_macho(path):
    if not os.path.isfile(path) or os.path.islink(path):
        return False
    with open(path, 'rb') as f:
        magic = f.read(4)
    return magic in (b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca')


def deps(path):
    out = sh('otool', '-L', path, capture=True).splitlines()[1:]
    res = []
    for line in out:
        d = line.strip().split(' (')[0]
        if d and not d.startswith('@') and not d.startswith(SYSTEM_PREFIXES):
            res.append(d)
    return res


def make_writable(p):
    os.chmod(p, os.stat(p).st_mode | stat.S_IWUSR)


def bundle_iverilog(app):
    prefix = os.path.realpath(sh('brew', '--prefix', 'icarus-verilog', capture=True).strip())
    # Resources, not Frameworks: Frameworks may only hold code, and Icarus also has .conf data files
    dst = os.path.join(app, 'Contents', 'Resources', 'iverilog')
    os.makedirs(os.path.join(dst, 'bin'), exist_ok=True)
    for exe in ('iverilog', 'vvp'):
        shutil.copy2(os.path.realpath(os.path.join(prefix, 'bin', exe)), os.path.join(dst, 'bin', exe))
    shutil.copytree(os.path.join(prefix, 'lib', 'ivl'), os.path.join(dst, 'lib', 'ivl'), symlinks=False,
                    dirs_exist_ok=True)
    libs = os.path.join(dst, 'libs')
    os.makedirs(libs, exist_ok=True)
    # Homebrew files are read-only; codesign and install_name_tool need to write them
    for dp, dns, fns in os.walk(dst):
        for n in dns + fns:
            make_writable(os.path.join(dp, n))

    queue = []
    for dp, _, fns in os.walk(dst):
        for fn in fns:
            p = os.path.join(dp, fn)
            if is_macho(p):
                queue.append(p)
    done = set()
    while queue:
        f = queue.pop()
        if f in done:
            continue
        done.add(f)
        make_writable(f)
        for d in deps(f):
            name = os.path.basename(d)
            local = os.path.join(libs, name)
            if not os.path.exists(local):
                shutil.copy2(os.path.realpath(d), local)
                make_writable(local)
                sh('install_name_tool', '-id', '@loader_path/' + name, local)
                queue.append(local)
            rel = os.path.relpath(libs, os.path.dirname(f))
            sh('install_name_tool', '-change', d, '@loader_path/' + rel + '/' + name, f)
    # ad-hoc sign every binary we touched (required on Apple Silicon)
    for f in sorted(done):
        sh('codesign', '--force', '--sign', '-', f)
    for f in sorted(done):
        left = deps(f)
        if left:
            sys.exit('still linked to non-bundled libraries: %s -> %s' % (f, left))
    print('bundled Icarus Verilog from', prefix)


def main():
    os.chdir(ROOT)
    shutil.rmtree(os.path.join(ROOT, 'build'), ignore_errors=True)
    shutil.rmtree(os.path.join(ROOT, 'dist'), ignore_errors=True)
    sh(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed',
       '--name', 'VeriNest',
       '--icon', os.path.join(HERE, 'verinest.icns'),
       '--osx-bundle-identifier', 'io.github.mortezapourhoseini.verinest',
       '--add-data', 'web:web',
       '--add-data', 'examples:examples',
       '--paths', ROOT,
       '--collect-submodules', 'verinest',
       '--collect-submodules', 'webview',
       os.path.join(ROOT, 'packaging', 'windows', 'verinest_app.py'))
    app = os.path.join(ROOT, 'dist', 'VeriNest.app')
    bundle_iverilog(app)

    # version + dark-mode friendly Info.plist entries
    plist = os.path.join(app, 'Contents', 'Info.plist')
    sh('plutil', '-replace', 'CFBundleShortVersionString', '-string', __version__, plist)
    sh('plutil', '-replace', 'CFBundleVersion', '-string', __version__, plist)
    sh('plutil', '-replace', 'NSHighResolutionCapable', '-bool', 'YES', plist)
    sh('plutil', '-replace', 'LSMinimumSystemVersion', '-string', '11.0', plist)
    # inner binaries are already signed one by one; now seal the bundle itself
    sh('codesign', '--force', '--sign', '-', app)
    sh('codesign', '--verify', '--verbose=2', app)

    # DMG with an Applications shortcut and a short note about Gatekeeper
    arch = 'apple-silicon' if platform.machine() == 'arm64' else 'intel'
    stage = os.path.join(ROOT, 'dist', 'dmg')
    os.makedirs(stage)
    sh('ditto', app, os.path.join(stage, 'VeriNest.app'))
    os.symlink('/Applications', os.path.join(stage, 'Applications'))
    shutil.copy(os.path.join(HERE, 'READ ME FIRST.txt'), stage)
    dmg = os.path.join(ROOT, 'dist', 'VeriNest-%s-macOS-%s.dmg' % (__version__, arch))
    sh('hdiutil', 'create', '-volname', 'VeriNest', '-srcfolder', stage, '-ov', '-format', 'UDZO', dmg)
    print('built', dmg)


if __name__ == '__main__':
    main()

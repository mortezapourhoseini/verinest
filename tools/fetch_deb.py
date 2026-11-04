#!/usr/bin/env python3
"""Download .deb files over HTTPS and verify their hashes.

Used by install.sh when `apt-get install` fails (for example when plain-HTTP
mirrors are blocked or return a filter page).

  fetch_deb.py <package>      one package; name and hash come from `apt-cache show`
  fetch_deb.py --uris FILE    a package with all its missing dependencies: FILE is the
                              output of `apt-get install --print-uris -qq <package>`

Prints the paths of the verified .deb files, one per line.
"""
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

MIRRORS = [
    'https://mirrors.edge.kernel.org/ubuntu',
    'https://archive.ubuntu.com/ubuntu',
    'https://mirror.arvancloud.ir/ubuntu',
    'https://mirror-linux.runflare.com/ubuntu',
    'https://ir.archive.ubuntu.com/ubuntu',
    'https://mirrors.kernel.org/ubuntu',
    'https://mirror.math.princeton.edu/pub/ubuntu',
    'https://ftp.halifax.rwth-aachen.de/ubuntu',
]

KNOWN = {
    'iverilog': ('pool/universe/i/iverilog/iverilog_12.0-2build2_amd64.deb',
                 'sha256', 'f19394cee05ad526e0eb3873bc6c17a5828f56df17fbe2db40cb66513a2d4667'),
}


def apt_record(pkg):
    try:
        out = subprocess.run(['apt-cache', 'show', '--no-all-versions', pkg],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return None
    fn = sha = None
    for line in out.splitlines():
        if line.startswith('Filename:') and fn is None:
            fn = line.split(':', 1)[1].strip()
        elif line.startswith('SHA256:') and sha is None:
            sha = line.split(':', 1)[1].strip()
        if not line.strip() and fn:
            break
    return (fn, 'sha256', sha) if fn and sha else None


def from_uris(path):
    """Parse `apt-get --print-uris` output: 'URL' name size HASHTYPE:hash"""
    items = []
    with open(path) as f:
        for line in f:
            m = re.match(r"'([^']+)'\s+(\S+)\s+\d+\s+(\w+):(\w+)", line.strip())
            if not m:
                continue
            url, algo, digest = m.group(1), m.group(3).lower(), m.group(4)
            k = url.find('/pool/')
            if k < 0:
                continue
            items.append((url[k + 1:], algo.replace('md5sum', 'md5'), digest))
    return items


order = list(MIRRORS)


def download(rel, algo, digest):
    dest = os.path.join(tempfile.gettempdir(), os.path.basename(rel))
    # unstable networks often drop TLS connections at random: go round the mirrors 3 times
    for m in list(order) * 3:
        try:
            print('  %s  <-  %s' % (os.path.basename(rel), m), file=sys.stderr)
            with urllib.request.urlopen(m + '/' + rel, timeout=25) as r:
                data = r.read()
        except Exception as e:  # noqa
            print('    failed: %s' % str(e)[:70], file=sys.stderr)
            continue
        if hashlib.new(algo, data).hexdigest() != digest:
            print('    wrong file (%d bytes, hash mismatch) - skipped' % len(data), file=sys.stderr)
            continue
        # try the mirror that worked first next time
        order.remove(m)
        order.insert(0, m)
        with open(dest, 'wb') as f:
            f.write(data)
        print('    ok, hash verified', file=sys.stderr)
        return dest
    return None


def main():
    if sys.argv[1] == '--uris':
        items = from_uris(sys.argv[2])
        if not items:
            print('nothing to download', file=sys.stderr)
            sys.exit(2)
    else:
        rec = apt_record(sys.argv[1]) or KNOWN.get(sys.argv[1])
        if not rec:
            print('no package information for %s' % sys.argv[1], file=sys.stderr)
            sys.exit(2)
        items = [rec]
    paths = []
    for rel, algo, digest in items:
        p = download(rel, algo, digest)
        if not p:
            print('could not download %s from any mirror' % os.path.basename(rel), file=sys.stderr)
            sys.exit(1)
        paths.append(p)
    print('\n'.join(paths))


if __name__ == '__main__':
    main()

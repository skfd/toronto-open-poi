"""Publish site/ to the orphan gh-pages branch as a single commit, force-pushed.

Each publish replaces the branch tip rather than adding to it, so a 15 MB
candidates.geojson rebuilt every week never accumulates in the repository. The
pattern is `toronto-parks-layer`'s: stage the built site in place with a temporary
index and GIT_WORK_TREE instead of copying it into a worktree.
"""
import os
import re
import subprocess
import time
from datetime import date

from src import config

GH_PAGES_INDEX = os.path.join(config.ROOT, '.gh-pages-index')

# The commit is written locally before the push is attempted, so a retry costs one
# round trip and giving up leaves the build on disk for a later `run.py publish`.
PUSH_RETRIES = 2
PUSH_WAIT = 60

# Only a network failure is worth retrying. A rejected push or a bad credential
# fails identically every time and should surface now, not in three minutes.
_NETWORK_ERR = re.compile(
    r'could not resolve host|unable to access|failed to connect'
    r'|connection timed out|operation timed out|connection reset',
    re.I,
)


def publish():
    if not os.path.isfile(os.path.join(config.SITE_DIR, 'index.html')):
        raise SystemExit("nothing built yet -- run 'python run.py build' first")

    env = {
        **os.environ,
        'GIT_DIR': os.path.join(config.ROOT, '.git'),
        'GIT_WORK_TREE': config.SITE_DIR,
        'GIT_INDEX_FILE': GH_PAGES_INDEX,
    }
    if os.path.exists(GH_PAGES_INDEX):
        os.remove(GH_PAGES_INDEX)

    print('staging %s ...' % config.SITE_DIR)
    _git(['add', '-A'], env)
    tree = _git(['write-tree'], env).strip()
    commit = _git(['commit-tree', tree, '-m', 'site %s' % date.today().isoformat()],
                  env).strip()
    _git(['update-ref', 'refs/heads/gh-pages', commit], env)
    print('gh-pages -> %s' % commit[:12])

    print('force-pushing gh-pages ...')
    _push(env)
    os.remove(GH_PAGES_INDEX)
    print('published.')


def _push(env):
    for attempt in range(PUSH_RETRIES + 1):
        try:
            _git(['push', '--force', 'origin', 'gh-pages'], env)
            return
        except RuntimeError as e:
            if not _NETWORK_ERR.search(str(e)) or attempt == PUSH_RETRIES:
                raise
            print('  push failed (%s); retrying in %ds'
                  % (str(e).splitlines()[-1], PUSH_WAIT))
            time.sleep(PUSH_WAIT)


def _git(args, env):
    result = subprocess.run(
        ['git', *args], cwd=config.ROOT, env=env,
        capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode != 0:
        raise RuntimeError('git %s failed (exit %d):\n%s'
                           % (' '.join(args), result.returncode, result.stderr.strip()))
    return result.stdout

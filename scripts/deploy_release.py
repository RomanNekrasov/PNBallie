#!/usr/bin/env python3
"""Propose only PNBallie image pins to GitOps, then verify the live release.

The repository-scoped SSH deploy key pushes a candidate branch. The homelab's
own workflow runs its required validation, creates a PR and merges it. No
cluster credentials or branch-protection bypass are used here.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request
import urllib.error

ORIGINS = {'acceptance': 'https://acceptatie.pnballie.nl', 'production': 'https://pnballie.nl'}


def git(folder, *args, check=True):
    return subprocess.run(['git', '-C', str(folder), *args], check=check, text=True, capture_output=True)


def validate(release):
    if set(release) != {'revision', 'schema', 'backend', 'frontend', 'source_run'}:
        raise ValueError('Unexpected release fields')
    assert re.fullmatch('[0-9a-f]{40}', release['revision'])
    assert re.fullmatch('[a-zA-Z0-9_]{1,32}', release['schema'])
    assert re.fullmatch(r'https://github.com/RomanNekrasov/PNBallie/actions/runs/[0-9]+', release['source_run'])
    for name in ('backend', 'frontend'):
        assert re.fullmatch('sha256:[0-9a-f]{64}', release[name])


def public_version(origin, path):
    request = urllib.request.Request(origin + path + '?check=' + str(time.time_ns()),
                                     headers={'User-Agent': 'PNBallie-delivery/1', 'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def live_matches(target, release):
    try:
        api = public_version(ORIGINS[target], '/api/version')
        frontend = public_version(ORIGINS[target], '/version.json')
        return (api['revision'] == frontend['revision'] == api.get('worker_revision') == release['revision']
                and api.get('schema') == release['schema'])
    except (OSError, ValueError, KeyError):
        return False


def prepare(folder, target, release):
    validate(release)
    if target not in ORIGINS:
        raise ValueError('Unknown deployment target')
    acceptance = folder / 'cluster/apps/pnballie-acceptance/release.json'
    if target == 'production':
        if not acceptance.is_file() or json.loads(acceptance.read_text()) != release:
            raise ValueError('Production must match the current acceptance release; approve the newest run')
        if not live_matches('acceptance', release):
            raise ValueError('Acceptance is not serving this complete release')
    namespace = 'pnballie-acceptance' if target == 'acceptance' else 'pnballie'
    path = folder / 'cluster/apps' / namespace
    for filename, service in [('backend.yaml', 'backend'), ('avatar-worker.yaml', 'backend'), ('frontend.yaml', 'frontend')]:
        file = path / filename
        text, count = re.subn(r'(image: ghcr\.io/romannekrasov/pnballie-' + service + r'@)sha256:[0-9a-f]{64}',
                             lambda m: m[1] + release[service], file.read_text())
        if not count:
            raise ValueError('Expected pinned images missing: ' + filename)
        if filename == 'avatar-worker.yaml':
            text = re.sub(r'fetchall\(\) == \[\("[a-zA-Z0-9_]+",\)\]',
                          'fetchall() == [("' + release['schema'] + '",)]', text)
        file.write_text(text)
    (path / 'release.json').write_text(json.dumps(release, indent=2) + '\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target', choices=ORIGINS, required=True)
    p.add_argument('--release', type=Path, required=True)
    p.add_argument('--repository', type=Path, required=True)
    args = p.parse_args()
    release = json.loads(args.release.read_text())
    folder = args.repository
    validate(release)
    run = os.environ['GITHUB_RUN_ID']; attempt = os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    assert run.isdecimal() and attempt.isdecimal()
    branch = f'pnballie-release/{args.target}/{release["revision"]}-{run}-{attempt}'
    git(folder, 'checkout', '-b', branch, 'origin/main')
    prepare(folder, args.target, release)
    git(folder, 'config', 'user.name', 'PNBallie delivery')
    git(folder, 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
    git(folder, 'add', 'cluster/apps/pnballie' + ('-acceptance' if args.target == 'acceptance' else ''))
    if not git(folder, 'diff', '--cached', '--quiet', check=False).returncode:
        if live_matches(args.target, release):
            print('Selected release is already live.')
            return
        raise RuntimeError('Release pins already selected but live verification failed; inspect Flux')
    git(folder, 'commit', '-m', f'deploy(pnballie): {args.target} {release["revision"][:12]}')
    git(folder, 'push', 'origin', branch)
    summary = Path(os.environ['GITHUB_STEP_SUMMARY'])
    with summary.open('a') as f:
        f.write(f'### {args.target}\n\nRelease `{release["revision"]}` → {ORIGINS[args.target]}\n\n'
                f'[GitOps pipeline](https://github.com/RomanNekrasov/spark-homelab/actions) · '
                f'[Release branch](https://github.com/RomanNekrasov/spark-homelab/tree/{branch})\n\n')
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        if live_matches(args.target, release):
            with summary.open('a') as f:
                f.write('API, frontend, worker heartbeat and database revision match the release.\n')
            print('Release is live: API, frontend, worker and schema match.', flush=True)
            return
        # If another GitOps merge advanced main during validation, merge it and
        # push through SSH again: this triggers real validation on the new head.
        git(folder, 'fetch', 'origin', 'main')
        if git(folder, 'merge-base', '--is-ancestor', 'origin/main', 'HEAD', check=False).returncode:
            if git(folder, 'merge-base', '--is-ancestor', 'HEAD', 'origin/main', check=False).returncode:
                git(folder, 'merge', '--no-edit', 'origin/main')
                if args.target == 'production' and json.loads((folder / 'cluster/apps/pnballie-acceptance/release.json').read_text()) != release:
                    raise RuntimeError('Acceptance moved to a newer release; approve its pipeline instead')
                git(folder, 'push', 'origin', branch)
        print('Waiting for protected GitOps checks, merge and Flux rollout…', flush=True)
        time.sleep(20)
    raise RuntimeError('Deployment verification timed out; inspect the linked GitOps pipeline')


if __name__ == '__main__':
    main()

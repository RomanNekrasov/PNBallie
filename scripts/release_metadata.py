#!/usr/bin/env python3
"""Create the immutable release descriptor from validated image build outputs."""
import ast
import json
import os
from pathlib import Path
import re


def schema_head(folder):
    revisions, parents = set(), set()
    for path in Path(folder).glob('*.py'):
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)] if isinstance(node, ast.Assign) else [node.target.id]
                if any(n in ('revision', 'down_revision') for n in names):
                    value = ast.literal_eval(node.value)
                    if 'revision' in names:
                        revisions.add(value)
                    elif value:
                        parents.update(value if isinstance(value, tuple) else [value])
    heads = revisions - parents
    if len(heads) != 1:
        raise ValueError('Release requires exactly one Alembic head')
    return heads.pop()


if __name__ == '__main__':
    revision = os.environ['IMAGE_SHA']
    assert re.fullmatch('[0-9a-f]{40}', revision)
    release = {'revision': revision, 'schema': schema_head('backend/alembic/versions'),
               'source_run': 'https://github.com/RomanNekrasov/PNBallie/actions/runs/' + os.environ['GITHUB_RUN_ID']}
    for service in ('backend', 'frontend'):
        digest = Path('image-' + service + '/digest.txt').read_text().strip()
        assert re.fullmatch('sha256:[0-9a-f]{64}', digest)
        release[service] = digest
    Path('release.json').write_text(json.dumps(release, indent=2) + '\n')

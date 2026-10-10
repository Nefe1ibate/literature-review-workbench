"""Install the bundled skill locally, without network access or overwriting files."""
import argparse
from pathlib import Path
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-dir', type=Path, default=Path.home() / '.agents' / 'skills',
                        help='Skill parent directory (default: ~/.agents/skills)')
    args = parser.parse_args()
    source = Path(__file__).resolve().parent / 'skills' / 'literature-review-workbench'
    destination = args.skills_dir.expanduser().resolve() / source.name
    if not (source / 'SKILL.md').is_file():
        parser.error('Bundled SKILL.md is missing; download the complete repository.')
    if destination.exists() or destination.is_symlink():
        parser.error(f'Destination already exists: {destination}. Back it up or choose another directory.')
    if destination == source or source in destination.parents or destination in source.parents:
        parser.error('Installation directory must be separate from the bundled skill.')
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    except OSError as error:
        print(f'Installation failed: {error}. Inspect any partial destination before retrying.', file=sys.stderr)
        return 1
    print(f'Installed: {destination}')
    print('In Codex, invoke $literature-review-workbench. Restart Codex if the skill does not appear.')
    return 0


if __name__ == '__main__':
    sys.exit(main())


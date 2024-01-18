"""updates translation sources and commits them commit by commit from CPython repository"""

from argparse import ArgumentParser
from contextlib import chdir
from dataclasses import dataclass
from logging import info, basicConfig
from os import PathLike
from pathlib import Path
from re import match
from shutil import move, rmtree
from subprocess import check_call, check_output, CalledProcessError
from tempfile import TemporaryDirectory

SYNC_COMMIT_FIELD = 'CPython-sync-commit-{}:'


def _update_pots(version: str) -> None:
    _ensure_working_tree_clean()
    if cpython_commit := _get_latest_sync_commit(version):
        info(f"Latest CPython sync commit found: {cpython_commit}")
        _clone_and_iterate_committing(cpython_commit, version)
    else:
        info("Latest CPython sync commit not found")
        _clone_and_commit(version)


def _ensure_working_tree_clean() -> None:
    try:
        _call('git diff --exit-code')
    except CalledProcessError as error:
        raise EnvironmentError('Working tree is not clean. Please commit or stash your changes.') from error


def _get_latest_sync_commit(version: str) -> str | None:
    _ensure_not_shallow()
    version_directory = Version(version).directory_name()
    sync_commit_field = SYNC_COMMIT_FIELD.format(version_directory)
    sync_commit_lines = [
        line for line in _get_latest_commit_message_containing(sync_commit_field) if line.startswith(sync_commit_field)
    ]
    if not sync_commit_lines:
        return
    return sync_commit_lines[0].removeprefix(f'{sync_commit_field} ')


def _ensure_not_shallow() -> None:
    if _output('git rev-parse --is-shallow-repository') == 'true\n':
        raise EnvironmentError('Repository is shallow, you could miss a sync commit in the log. Aborting.')


def _get_latest_commit_message_containing(phrase: str) -> list[str]:
    return _output(f'git log --grep {phrase} --pretty=format:"%B" --max-count=1').splitlines()


@dataclass
class Version:
    number: str

    def is_latest(self):
        return self.number == "3.12"

    def weblate_category_name(self):
        return self.number

    def directory_name(self):
        return self.is_latest() and "latest" or self.number


def _clone_and_iterate_committing(cpython_commit, version) -> None:
    version_directory = Version(version).directory_name()
    with TemporaryDirectory() as directory:
        with chdir(directory):
            _clone_cpython_repo(version, shallow=False)
            commits = _output(f'git -C cpython/ log --pretty=format:"%H" --reverse {cpython_commit}..')
        for commit in commits.splitlines():
            with chdir(directory):
                _call(f'git -C cpython/ checkout {commit}')
                _call('make -C cpython/Doc/ venv')
                _build_gettext()
                commit_message = _output('git -C cpython/ log --pretty=format:"%B" --max-count=1')
            pot_directory = Path(directory, 'cpython/Doc/locales/pot')
            _replace_tree(pot_directory, Path('.pot', version_directory))
            _commit_changed(commit_message, commit, version_directory)


def _clone_and_commit(version: str):
    version_directory = Version(version).directory_name()
    # if latest sync commit not found, checkout the HEAD
    with TemporaryDirectory() as directory:
        with chdir(directory):
            _clone_cpython_repo(version, shallow=True)
            _call('make -C cpython/Doc/ venv')
            _build_gettext()
            cpython_commit = _output('git -C cpython/ rev-parse HEAD')
        pot_directory = Path(directory, 'cpython/Doc/locales/pot')
        _replace_tree(pot_directory, Path('.pot', version_directory))
    _commit_changed("Update sources", cpython_commit, version_directory)


def _clone_cpython_repo(version: str, shallow: bool):
    _call(
        f'git clone -b {version} --single-branch https://github.com/python/cpython.git'
        + (' --depth 1' if shallow else '')
    )


def _build_gettext():
    _call(
        "make -C cpython/Doc/ ALLSPHINXOPTS='-E -b gettext -D gettext_compact=0 -d build/.doctrees . locales/pot' build"
    )


def _replace_tree(source: PathLike, target: Path):
    if target.exists():
        rmtree(target)
    move(source, target)


def _commit_changed(commit_message: str, commit: str, version: str) -> None:
    changed = _get_changed_pots()
    added = _get_new_pots()
    if all_ := changed + added:
        _call(f'git add {" ".join(all_)}')
        check_call(('git', 'commit', '-m', f'{commit_message}\n\n{SYNC_COMMIT_FIELD.format(version)} {commit}'))
    _call('git restore .')  # discard ignored files


def _get_changed_pots() -> list[str]:
    diff = _output("git diff -I'^\"POT-Creation-Date: ' --numstat")
    return [match(r'\d+\t\d+\t(.*)', line).group(1) for line in diff.splitlines()]


def _get_new_pots() -> list[str]:
    ls_files = _output('git ls-files -o -d --exclude-standard')
    return ls_files.splitlines()


def _call(command: str) -> None:
    check_call(command, shell=True)


def _output(command: str) -> str:
    return check_output(command, shell=True).decode()


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('version')
    options = parser.parse_args()

    basicConfig(level='INFO')

    _update_pots(options.version)

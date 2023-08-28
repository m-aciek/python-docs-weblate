"""updates translation sources and commits them"""

from argparse import ArgumentParser
from contextlib import chdir
from logging import info, basicConfig
from os import PathLike
from pathlib import Path
from re import match
from shutil import move, rmtree
from subprocess import check_call, check_output
from tempfile import TemporaryDirectory


def _update_pots(version: str) -> None:
    _call('git diff --exit-code')  # ensure working tree clean
    sync_commit_lines = [
        line for line
        in _output('git log --grep CPython-sync-commit: --pretty=format:"%B" --max-count=1').splitlines()
        if line.startswith('CPython-sync-commit: ')
    ]
    if sync_commit_lines:
        cpython_commit_line, *_ = sync_commit_lines
        cpython_commit = cpython_commit_line.removeprefix('CPython-sync-commit: ')
        info(f"Latest CPython sync commit found: {cpython_commit}")
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
                _replace_tree(Path(directory, 'cpython/Doc/locales/pot'), '.pot')
                _commit_changed(commit, commit_message)

    else:
        info("Latest CPython sync commit not found")
        # if latest sync commit not found, checkout the HEAD
        with TemporaryDirectory() as directory:
            with chdir(directory):
                _clone_cpython_repo(version, shallow=True)
                _call('make -C cpython/Doc/ venv')
                _build_gettext()
                cpython_commit = _output('git -C cpython/ rev-parse HEAD')
            _replace_tree(Path(directory, 'cpython/Doc/locales/pot'), '.pot')
        _commit_changed("Update sources", cpython_commit)


def _clone_cpython_repo(version: str, shallow: bool):
    _call(
        f'git clone -b {version} --single-branch https://github.com/python/cpython.git'
        + (' --depth 1' if shallow else '')
    )


def _build_gettext():
    _call(
        "make -C cpython/Doc/ ALLSPHINXOPTS='-E -b gettext -D gettext_compact=0 -d build/.doctrees . locales/pot' build"
    )


def _replace_tree(source: PathLike, target: PathLike):
    rmtree(target)
    move(source, target)


def _commit_changed(commit_message: str, commit: str) -> None:
    changed = _get_changed_pots()
    added = _get_new_pots()
    if all_ := changed + added:
        _call(f'git add {" ".join(all_)}')
        _call(f'git commit -m "{commit_message}\n\nCPython-sync-commit: {commit}"')
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

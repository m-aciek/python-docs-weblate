from argparse import ArgumentParser
from contextlib import chdir
from os import PathLike
from pathlib import Path
from re import match
from shutil import move, rmtree
from subprocess import call, run
from tempfile import TemporaryDirectory


def _update_pots(version: str) -> None:
    """updates translation sources and commits them"""
    _call('git diff --exit-code')
    with TemporaryDirectory() as directory:
        with chdir(directory):
            _clone_cpython_repo(version)
            _call('make -C cpython/Doc/ venv')
            _build_gettext()
        _replace_tree(Path(directory, 'cpython/Doc/locales/pot'), '.pot')
    changed = _get_changed_pots()
    added = _get_new_pots()
    if all_ := changed + added:
        _call(f'git add {" ".join(all_)}')
        _call('git commit -m "Update sources"')
    _call('git restore .')  # discard ignored files


def _clone_cpython_repo(version: str):
    _call(f'git clone -b {version} --single-branch https://github.com/python/cpython.git --depth 1')


def _build_gettext():
    _call(
        "make -C cpython/Doc/ ALLSPHINXOPTS='-E -b gettext -D gettext_compact=0 -d build/.doctrees . locales/pot' build"
    )


def _replace_tree(source: PathLike, target: PathLike):
    rmtree(target)
    move(source, target)


def _get_changed_pots() -> list[str]:
    diff = _run("git diff -I'^\"POT-Creation-Date: ' --numstat")
    return [match(r'\d+\t\d+\t(.*)', line).group(1) for line in diff.splitlines()]


def _get_new_pots() -> list[str]:
    ls_files = _run('git ls-files -o -d --exclude-standard')
    return ls_files.splitlines()


def _call(command: str):
    if (return_code := call(command, shell=True)) != 0:
        exit(return_code)


def _run(command: str) -> str:
    if (process := run(command, shell=True, capture_output=True)).returncode != 0:
        exit(process.returncode)
    return process.stdout.decode()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument('version')
    options = parser.parse_args()

    _update_pots(options.version)

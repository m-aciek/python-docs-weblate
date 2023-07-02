from argparse import ArgumentParser
from contextlib import chdir
from pathlib import Path
from shutil import rmtree, move
from subprocess import call
from tempfile import TemporaryDirectory

VERSION = '3.12'


def update_pots() -> None:
    """updates translation sources"""
    _call('git diff --exit-code')
    with TemporaryDirectory() as directory:
        with chdir(directory):
            _clone_cpython_repo(VERSION)
            _build_gettext()
        rmtree('.pot')
        move(Path(directory) / 'cpython/Doc/locales/pot', '.pot')
    if (call("git diff -I'^\"POT-Creation-Date: ' --exit-code", shell=True)) != 0:
        _call('git add .')
        _call('git commit -m "Update sources"')


def _clone_cpython_repo(version: str):
    _call(f'git clone -b {version} --single-branch https://github.com/python/cpython.git --depth 1')


def _build_gettext():
    _call(
        "make -C cpython/Doc/ ALLSPHINXOPTS='-E -b gettext -D gettext_compact=0 -d build/.doctrees . locales/pot' build"
    )


def _call(command: str):
    if (return_code := call(command, shell=True)) != 0:
        exit(return_code)


if __name__ == "__main__":
    RUNNABLE_SCRIPTS = ('update_pots', )

    parser = ArgumentParser()
    parser.add_argument('cmd', choices=RUNNABLE_SCRIPTS)
    options = parser.parse_args()

    eval(options.cmd)()

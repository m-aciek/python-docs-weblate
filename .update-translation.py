"""updates translation files for a language from the Weblate project and commits them"""

from argparse import ArgumentParser
from logging import info, basicConfig, warning
from os import getenv
from pathlib import Path
from re import match
from shutil import rmtree
from subprocess import call, run

from tqdm import tqdm
from wlc import Translation, Weblate, Project, WeblateException, WeblateThrottlingError


def _update_translation(language: str, weblate_key: str) -> None:
    _call('git diff --exit-code')
    _clear_files()
    _download_translations(language, weblate_key)
    changed = _get_changed_files()
    added = _get_new_files()
    if all_ := changed + added:
        _call(f'git add {" ".join(all_)}')
        _call('git commit -m "Update translation from Weblate"')
    _call('git restore .')  # discard ignored files


def _clear_files():
    for path in Path().iterdir():
        if path.name.startswith('.'):
            continue
        if path.is_dir() and not path.is_symlink():
            rmtree(path)
        if path.suffix == '.po':
            path.unlink()


def _download_translations(language: str, weblate_key: str) -> None:
    weblate = Weblate(weblate_key, 'https://hosted.weblate.org/api/')
    project = Project(weblate, 'https://hosted.weblate.org/api/projects/python-docs/')
    for component in tqdm(project.list()):
        if component.is_glossary:
            continue
        url = f'https://hosted.weblate.org/api/translations/python-docs/{component.slug}/{language}/'
        try:
            content = Translation(weblate, url).download()
        except WeblateThrottlingError:
            info(f'Skipped {component.slug} due to throttling')
        except WeblateException as exc:
            if str(exc) == 'Object not found on the server (maybe operation is not supported on the server)':
                info(f"{component.slug} doesn't have a {language} translation")
                continue
            raise
        else:
            path = Path(component.filemask.removeprefix('*/'))
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(content)


def _get_changed_files() -> list[str]:
    diff = _run("git diff -I'^\"POT-Creation-Date: ' --numstat")
    return [match(r'\d+\t\d+\t(.*)', line).group(1) for line in diff.splitlines()]


def _get_new_files() -> list[str]:
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
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('language')
    options = parser.parse_args()

    basicConfig(level='INFO')

    if not (weblate_key := getenv('KEY')):
        warning('Not authenticated, you will be heavy throttled')

    _update_translation(options.language, weblate_key=weblate_key)

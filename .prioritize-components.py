from os import getenv

from tqdm import tqdm
from wlc import Weblate, Project, Translation

HIGH_PRIORITY = 80


def _prioritize_components(weblate_key: str) -> None:
    weblate = Weblate(weblate_key, 'https://hosted.weblate.org/api/')
    project = Project(weblate, 'https://hosted.weblate.org/api/projects/python-docs/')
    for component in tqdm(project.list()):
        if component.name == "bugs" or component.name.startswith("tutorial") or component.name == "library/functions":
            component.patch(priority=HIGH_PRIORITY)


if __name__ == "__main__":
    _prioritize_components(weblate_key=getenv('KEY'))

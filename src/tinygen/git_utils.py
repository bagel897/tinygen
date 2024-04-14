from git import Repo
from tinygen.consts import SUPPORTED_TYPES


def get_files(tree):
    for entry in tree:
        if entry.type == "tree":
            yield from get_files(entry)
        else:
            if entry.name.endswith(tuple(SUPPORTED_TYPES)):

                yield entry.path


def get_diff(repo: Repo):
    diff = repo.index.diff(None, create_patch=True, unified=1000)
    result = ""
    for diff in diff.iter_change_type("M"):
        result += str(diff)
    return result


def reset_repo(repo: Repo):
    repo.git.reset("--hard")
    repo.git.clean("-fd")

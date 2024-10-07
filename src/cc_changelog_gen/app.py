from argparse import ArgumentParser
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum, StrEnum, auto
from git import Repo, TagReference
import os.path
from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    YamlConfigSettingsSource,
)
import re
import semver
import sys
from typing import Dict, List, Optional, Tuple, Type

ALLOWED_SCHEME = ["file", "http", "https"]


class SchemeException(Exception):
    def __init__(self, scheme: str):
        self.scheme = scheme

    def __str__(self) -> str:
        return f"Invalid scheme '{self.scheme}' to retrieve content from"


class Color(StrEnum):
    WARNING = "\033[93m"
    ENDC = "\033[0m"


def print_color(color: Color, text: str, file=sys.stdout):
    print(f"{color}{text}{Color.ENDC}", file=file)


@dataclass
class Args:
    commits: str
    title: str
    conf: str
    repo: str


class Processing(BaseModel):
    search: str
    replace: str


class Conf(BaseSettings):
    pre_captures: List[str] = field(default_factory=list)
    pre_captures_after_trim: str = r"\s+"
    type_captures: List[str] = field(default_factory=list)
    type_captures_after_trim: str = r"\s+"
    type_captures_allow_breaking_change_group: bool = True
    breaking_change_line_captures: List[str] = field(default_factory=list)
    breaking_change_line_captures_after_trim: str = r"\s+"
    title_left_trim: str = r"\s+"
    title_right_trim: str = r"\s+"
    supported_types: Dict[str, str] = field(default_factory=dict)
    headings: OrderedDict[str, str] = field(default_factory=dict)
    others_heading: str = "Others"
    breaking_changes_heading: str = "BREAKING CHANGES"
    capitalize_title_first_char: bool = True
    preprocessing: Optional[Processing] = None
    postprocessing: Optional[Processing] = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        # TODO: No better way to pass in runtime value until source changes:
        # https://github.com/pydantic/pydantic-settings/issues/259
        global YAML_FILE_PATH
        return (YamlConfigSettingsSource(settings_cls, yaml_file=YAML_FILE_PATH),)


class TypeMatch(Enum):
    SUPPORTED_TYPE = auto()
    OTHERS = auto()


@dataclass
class TypeCaptureOutput:
    title: str
    type_capture: str
    type_match: TypeMatch
    is_breaking_change: bool


@dataclass
class MarkdownContent:
    values: Dict[str, List[str]]
    others: List[str]
    breaking_changes: List[str]

    def __init__(
        self,
        values: Dict[str, List[str]] = dict(),
        others: List[str] = list(),
        breaking_changes: List[str] = list(),
    ):
        self.values = values
        self.others = others
        self.breaking_changes = breaking_changes

    def get_values(self, heading: str) -> List[str]:
        if heading not in self.values:
            self.values[heading] = []

        return self.values[heading]


def args_parse() -> Args:
    parser = ArgumentParser(
        prog="Changelog Generator",
        description="Supports Conventional Commit styled messages to extract for dumping to CHANGELOG",
    )
    parser.add_argument("commits")
    parser.add_argument("-t", "--title", default="vX.Y.Z")
    parser.add_argument("-c", "--conf", default=".clog.yaml")
    parser.add_argument("-r", "--repo", default=".")
    return Args(**vars(parser.parse_args()))


def latest_semver(versions: Dict[str, semver.Version]) -> Optional[str]:
    return max(versions, key=versions.get) if versions else None


def closest_previous_semver(
    target: semver.Version, versions: Dict[str, semver.Version]
) -> Optional[str]:
    # To store all versions smaller than target
    candidates: Dict[str, semver.Version] = dict()

    for tag, version in versions.items():
        if version < target:
            candidates[tag] = version

    # The largest smaller-than target semver gives the closest previous
    return latest_semver(candidates)


def process_commits_str(
    commits_str: str, release_title: str, repo_tags: List[TagReference]
):
    def _clean_tag(possible_tag: str) -> str:
        return re.sub(r"^[vV]", "", possible_tag)

    if commits_str.startswith("~.."):
        title_tag_raw = _clean_tag(release_title)

        tag_versions = {
            t.name: semver.Version.parse(_clean_tag(t.name))
            for t in repo_tags
            if semver.Version.is_valid(_clean_tag(t.name))
        }

        if semver.Version.is_valid(title_tag_raw):
            title_tag = semver.Version.parse(title_tag_raw)
            closest_prev_tag = closest_previous_semver(title_tag, tag_versions)

            if closest_prev_tag:
                # Found closest semver tags to valid semver release title
                commits_str = re.sub(r"^~", closest_prev_tag, commits_str)
                print_color(
                    Color.WARNING,
                    f"Using commit range '{commits_str}'",
                    file=sys.stderr,
                )
            else:
                # Start from beginning if there are no valid semver tags
                commits_str = re.sub(r"^~\.\.", "", commits_str)
                print_color(
                    Color.WARNING,
                    f"No valid semver tags found, starting from beginning to commit '{commits_str}'",
                    file=sys.stderr,
                )
        else:
            latest_tag = latest_semver(tag_versions)

            if latest_tag:
                # Use latest valid semver tag if not provided with valid release title semver
                commits_str = re.sub(r"^~", latest_tag, commits_str)
                print_color(
                    Color.WARNING,
                    f"Release title is not a valid semver, using latest semver tag '{commits_str}'",
                    file=sys.stderr,
                )
            else:
                # Start from beginning if no valid tags from release title and tags
                commits_str = re.sub(r"^~\.\.", "", commits_str)
                print_color(
                    Color.WARNING,
                    f"No valid semver release title or tags found, starting from beginning to commit '{commits_str}'",
                    file=sys.stderr,
                )

    return commits_str


def process_markdown(
    mdc: MarkdownContent,
    title: str,
    headings: OrderedDict[str, str],
    others_heading: str,
    breaking_changes_heading: str,
) -> str:
    def _append_points(points: List[str]):
        return "\n".join(map(lambda p: f"- {p}", points))

    def _append_section(heading: str, points: List[str]):
        return f"## {heading}\n\n{_append_points(points)}\n"

    content = f"# {title}\n\n"

    for heading_key, heading in headings.items():
        if heading_key in mdc.values:
            content += _append_section(heading, mdc.values[heading_key]) + "\n"

    if len(mdc.others) > 0:
        content += _append_section(others_heading, mdc.others) + "\n"

    if len(mdc.breaking_changes) > 0:
        content += _append_section(breaking_changes_heading, mdc.breaking_changes)

    return content


def enhance_title(title: str, capitalize_title_first_char: bool) -> str:
    return title.capitalize() if capitalize_title_first_char else title


def process_pre_capture(
    title: str, pre_captures: List[str], pre_captures_after_trim: bool
) -> str:
    already_pre_captured = False

    for pc in pre_captures:
        if already_pre_captured:
            break

        pre_capture_match = re.match(rf"^{pc}", title)

        if pre_capture_match:
            already_pre_captured = True
            title = re.split(rf"^{pc}", title)[1]
            title = re.sub(rf"^{pre_captures_after_trim}", "", title)

    return title


def process_type_capture(
    title: str,
    type_captures: List[str],
    type_captures_after_trim: str,
    type_captures_allow_breaking_change_group: bool,
    title_left_trim: str,
    title_right_trim: str,
    supported_types: Dict[str, str],
    capitalize_title_first_char: bool,
) -> TypeCaptureOutput:
    type_capture = ""
    already_type_captured = False
    is_breaking_change = False

    for tc in type_captures:
        if already_type_captured:
            break

        type_capture_match = re.match(rf"^{tc}", title)

        if type_capture_match:
            already_type_captured = True
            type_capture = type_capture_match.group(1)

            if (
                type_captures_allow_breaking_change_group
                and len(type_capture_match.groups()) >= 2
            ):
                is_breaking_change = True

            title = re.split(rf"^{tc}", title)[-1]
            title = re.sub(rf"^{type_captures_after_trim}", "", title)

            if type_capture in supported_types.keys():
                type_match = TypeMatch.SUPPORTED_TYPE
            else:
                type_match = TypeMatch.OTHERS

    if not already_type_captured:
        type_match = TypeMatch.OTHERS

    title = re.sub(rf"^{title_left_trim}", "", title)
    title = re.sub(rf"{title_right_trim}$", "", title)
    title = enhance_title(title, capitalize_title_first_char)

    return TypeCaptureOutput(
        title=title,
        type_capture=type_capture,
        type_match=type_match,
        is_breaking_change=is_breaking_change,
    )


def process_breaking_change(
    messages: str,
    breaking_change_line_captures: List[str],
    breaking_change_line_captures_after_trim: str,
    capitalize_title_first_char: bool,
) -> str:
    for bc in breaking_change_line_captures:
        for msg in messages:
            breaking_change_line_match = re.match(rf"^{bc}", msg)

            if breaking_change_line_match:
                msg = re.split(rf"^{bc}", msg)[1]
                msg = re.sub(rf"^{breaking_change_line_captures_after_trim}", "", msg)
                msg = enhance_title(msg, capitalize_title_first_char)
                return msg

    return None


def main():
    args = args_parse()

    try:
        global YAML_FILE_PATH
        YAML_FILE_PATH = args.conf
        if not os.path.isfile(YAML_FILE_PATH):
            raise FileNotFoundError(YAML_FILE_PATH)
    except OSError:
        print_color(
            Color.WARNING,
            f"Missing '{args.conf}' config file, using default values...",
            file=sys.stderr,
        )

    c = Conf()
    repo = Repo(args.repo)

    # Commit parsing to find nearest previous semver tag
    commits_str = process_commits_str(
        commits_str=args.commits, release_title=args.title, repo_tags=repo.tags
    )

    commits = list(repo.iter_commits(f"{commits_str}"))
    mdc = MarkdownContent()

    for cm in commits:
        messages = cm.message.split("\n")
        title = messages[0]

        if c.preprocessing:
            title = re.sub(c.preprocessing.search, c.preprocessing.replace, title)

        # Pre-capture logic
        title = process_pre_capture(
            title=title,
            pre_captures=c.pre_captures,
            pre_captures_after_trim=c.pre_captures_after_trim,
        )

        # Type capture logic
        breaking_change_title = None

        type_capture_output = process_type_capture(
            title=title,
            type_captures=c.type_captures,
            type_captures_after_trim=c.type_captures_after_trim,
            type_captures_allow_breaking_change_group=c.breaking_change_line_captures_after_trim,
            title_left_trim=c.title_left_trim,
            title_right_trim=c.title_right_trim,
            supported_types=c.supported_types,
            capitalize_title_first_char=c.capitalize_title_first_char,
        )

        title = type_capture_output.title

        if c.postprocessing:
            title = re.sub(c.postprocessing.search, c.postprocessing.replace, title)

        match type_capture_output.type_match:
            case TypeMatch.SUPPORTED_TYPE:
                heading = c.supported_types[type_capture_output.type_capture]
                mdc.get_values(heading).append(title)
            case TypeMatch.OTHERS:
                mdc.others.append(title)

        if type_capture_output.is_breaking_change:
            breaking_change_title = title

        # Additional breaking change logic
        breaking_change_title_explicit = process_breaking_change(
            messages=messages,
            breaking_change_line_captures=c.breaking_change_line_captures,
            breaking_change_line_captures_after_trim=c.breaking_change_line_captures_after_trim,
            capitalize_title_first_char=c.capitalize_title_first_char,
        )

        breaking_change_title = (
            breaking_change_title_explicit
            if breaking_change_title_explicit
            else breaking_change_title
        )

        if breaking_change_title:
            mdc.breaking_changes.append(breaking_change_title)

    md = process_markdown(
        mdc, args.title, c.headings, c.others_heading, c.breaking_changes_heading
    )

    print(md)


if __name__ == "__main__":
    main()

from argparse import ArgumentParser
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum, auto
from git import Repo
import re
from typing import Dict, List
import yaml


@dataclass
class Conf:
    pre_captures: List[str] = field(default_factory=list)
    pre_captures_after_trim: str = r"\s+"
    type_captures: List[str] = field(default_factory=list)
    type_captures_after_trim: str = r"\s+"
    type_captures_allow_breaking_change_group: bool = True
    breaking_change_line_captures: List[str] = field(default_factory=list)
    breaking_change_line_captures_after_trim: str = r"\s+"
    supported_types: Dict[str, str] = field(default_factory=dict)
    headings: OrderedDict[str, str] = field(default_factory=dict)
    others_heading: str = "Others"
    breaking_changes_heading: str = "BREAKING CHANGES"
    capitalize_title_first_char: bool = True


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

            title = enhance_title(title, capitalize_title_first_char)

    if not already_type_captured:
        title = enhance_title(title, capitalize_title_first_char)
        type_match = TypeMatch.OTHERS

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


def args_parse():
    parser = ArgumentParser(
        prog="Changelog Generator",
        description="Supports Conventional Commit styled messages to extract for dumping to CHANGELOG",
    )
    parser.add_argument("commits")
    parser.add_argument("-t", "--title", default="REPLACE_WITH_YOUR_RELEASE_TAG")
    parser.add_argument("-c", "--conf", default=".clgen.yaml")
    parser.add_argument("-r", "--repo", default=".")
    return parser.parse_args()


def main():
    args = args_parse()

    # YAML
    with open(args.conf, "r") as f:
        conf_dict = yaml.safe_load(f)

    c = Conf(**conf_dict)

    repo = Repo(args.repo)
    commits = list(repo.iter_commits(f"{args.commits}"))

    mdc = MarkdownContent()

    for cm in commits:
        messages = cm.message.split("\n")
        title = messages[0]

        # Pre-capture logic
        title = process_pre_capture(title, c.pre_captures, c.pre_captures_after_trim)

        # Type capture logic
        breaking_change_title = None

        type_capture_output = process_type_capture(
            title=title,
            type_captures=c.type_captures,
            type_captures_after_trim=c.type_captures_after_trim,
            type_captures_allow_breaking_change_group=c.breaking_change_line_captures_after_trim,
            supported_types=c.supported_types,
            capitalize_title_first_char=c.capitalize_title_first_char,
        )

        title = type_capture_output.title

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

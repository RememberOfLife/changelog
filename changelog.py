#!/usr/bin/env python3
from enum import Enum
import argparse
import json
import os
import sys


SCR_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCR_DIR)
# local chevron copy, make the import less hacky
import chevron # https://github.com/noahmorrison/chevron


class Change(Enum):
    FEATURE = 1
    INLINE_TEXT = 2
    ADD = 3
    CHANGE = 4
    REMOVE = 5
    FIX = 6

    def html_type_class(self):
        return ["highlight", "inline-text", "added", "changed", "removed", "fixed"][self.value - 1]
    
    def html_entity(self):
        return ["&starf;", None, "+", "&bull;", "&ndash;", "&times;"][self.value - 1]


def parse_change_type(text):
    if len(text) < 3:
        raise ValueError
    breaking = False
    type_char = text[0]
    assert_space = text[1]
    if type_char == "!":
        breaking = True
        type_char = text[1]
        if (len(text) < 4):
            raise ValueError
        assert_space = text[2]
    if assert_space != " ":
        raise ValueError
    if type_char == "*":
        return (Change.FEATURE, breaking)
    elif type_char == "?":
        return (Change.INLINE_TEXT, breaking)
    elif type_char == "+":
        return (Change.ADD, breaking)
    elif type_char == ":":
        return (Change.CHANGE, breaking)
    elif type_char == "-":
        return (Change.REMOVE, breaking)
    elif type_char == "x":
        return (Change.FIX, breaking)
    else:
        raise ValueError


def parse_change_line(line, allow_breaking, allow_features, only_features, all_breaking):
    change_type = None
    breaking = False
    text = None
    refs = []
    if type(line) is str:
        text = line
    elif type(line) is list:
        if len(line) < 1:
            raise ValueError
        text = line[0]
        refs = line[1:]
    elif type(line) is dict:
        text = line["d"]
        if "c" in line:
            drefs = line["c"]
            if type(drefs) is str:
                refs.append(drefs)
            elif type(drefs) is list:
                refs = drefs
            else:
                raise ValueError
    else:
        raise ValueError
    change_type, breaking = parse_change_type(text)
    if change_type in [Change.FEATURE, Change.INLINE_TEXT] and (breaking or len(refs) > 0):
        raise ValueError
    if not allow_breaking and breaking:
        raise ValueError
    if not allow_features and change_type == Change.FEATURE:
        raise ValueError
    if only_features and change_type != Change.FEATURE:
        raise ValueError
    return (change_type, breaking or all_breaking, text[2+(1 if breaking else 0):], refs)


def parse_changelog(path):
    json_file = open(path, "r")
    #TODO pre-process to allow for json comments and trailing commas
    changelog = json.load(json_file)
    project = changelog["project"]
    parsed_versions = []
    for version in changelog["versions"]:
        new_version = {
            "version": version["version"],
            "date": version["date"],
            "name": None,
            "blocks": [],
        }
        blocks = []
        if "name" in version and type(version["name"] is str):
            new_version["name"] = version["name"]
        if "changes" in version:
            # auto-block
            lines_features = []
            lines_breaking = []
            lines_general = []
            lines_fixes = []
            for line in version["changes"]:
                parsed_line = parse_change_line(line, True, True, False, False)
                #TODO auto-sort into *different* blocks feature can be turned off
                #TODO possibly we do not want to allow inline text in auto-block mode
                #TODO auto-sort for breaking and general, i.e. inlinetext>add>change>remove>fix
                if parsed_line[0] is Change.FEATURE:
                    lines_features.append(parsed_line)
                elif parsed_line[1] is True:
                    lines_breaking.append(parsed_line)
                elif parsed_line[0] is Change.FIX:
                    lines_fixes.append(parsed_line)
                else:
                    lines_general.append(parsed_line)
            if len(lines_features) > 0:
                blocks.append({
                    "name": None,
                    "breaking": False,
                    "pure_text": False,
                    "lines": lines_features,
                })
            if len(lines_breaking) > 0:
                blocks.append({
                    "name": None,
                    "breaking": True,
                    "pure_text": False,
                    "lines": lines_breaking,
                })
            if len(lines_general) > 0:
                blocks.append({
                    "name": None,
                    "breaking": False,
                    "pure_text": False,
                    "lines": lines_general,
                })
            if len(lines_fixes) > 0:
                blocks.append({
                    "name": None,
                    "breaking": False,
                    "pure_text": False,
                    "lines": lines_fixes,
                })
        elif "blocks" in version:
            seen_highlights = False
            seen_breaking = False
            for block in version["blocks"]:
                parsed_block = {
                    "name": None,
                    "breaking": False,
                    "pure_text": False,
                    "lines": [],
                }
                if "name" in block and type(block["name"] is str):
                    parsed_block["name"] = block["name"]
                if "text" in block and type(block["text"] is list):
                    parsed_block["pure_text"] = True
                    parsed_block["lines"] = block["text"]
                elif "highlights" in block and type(block["highlights"] is list):
                    if seen_highlights:
                        raise ValueError
                    seen_highlights = True
                    for line in block["highlights"]:
                        parsed_block["lines"].append(parse_change_line(line, False, True, True, False))
                elif "breaking" in block and type(block["breaking"] is list):
                    if seen_breaking:
                        raise ValueError
                    seen_breaking = True
                    parsed_block["breaking"] = True
                    for line in block["breaking"]:
                        parsed_block["lines"].append(parse_change_line(line, True, False, False, True))
                elif "changes" in block and type(block["changes"] is list):
                    for line in block["changes"]:
                        parsed_block["lines"].append(parse_change_line(line, False, False, False, False))
                else:
                    raise ValueError
                blocks.append(parsed_block)
        else:
            raise ValueError
        new_version["blocks"] = blocks
        parsed_versions.append(new_version)
    return (project, parsed_versions)


def make_template_data(project, versions, max_num):
    rtd = {
        "page_title": f"{project} Changelog {versions[0]["version"] if len(versions) == 1 else "ALL"}",
        "project_name": project,
        "versions": [],
    }
    ctr = max_num
    for version in versions:
        template_version = {
            "num": ctr,
            "name": version["name"],
            "version": version["version"],
            "date": version["date"],
            "blocks": [],
        }
        ctr -= 1
        for block in version["blocks"]:
            template_block = {
                "breaking": block["breaking"],
                "name": block["name"],
                "pure_text": block["pure_text"],
                "lines": []
            }
            if block["pure_text"]:
                template_block["lines"] = block["lines"]
            else:
                for line in block["lines"]:
                    template_line = {
                        "type": line[0].html_type_class(),
                        "prefix": line[0].html_entity(),
                        "text": line[2],
                        "refs": None if len(line[3]) == 0 else "<br>".join([f"[{tl[0:6]}]" for tl in line[3]]),
                    }
                    template_block["lines"].append(template_line)
            template_version["blocks"].append(template_block)
        rtd["versions"].append(template_version)
    return rtd


def generate_pretty(project, parsed_versions, path):
        ctr = len(parsed_versions)
        for version in parsed_versions:
            changelog_template_data = make_template_data(project, [version], ctr)
            ctr -= 1
            with open(f"{SCR_DIR}/changelog.html.mst", "r") as changelog_template:
                rendered_changelog = chevron.render(changelog_template, changelog_template_data)
                #TODO sanitize version string as a filename?
                with open(f"{path}/{changelog_template_data["versions"][0]["num"]}_{version["version"]}.html", "w") as version_file:
                    version_file.write(rendered_changelog)


def main(args):
    parser = argparse.ArgumentParser(prog="changelog.py")
    parser.add_argument("changelog")
    parser.add_argument("outdir")
    parser.add_argument("--rit", dest="readin_test", action="store_true")
    parser.add_argument("--acs-sort-type", dest="acs_sort_type", action="store_true")
    args = parser.parse_args()

    project, parsed_versions = parse_changelog(args.changelog)

    # debug print
    if args.readin_test:
        print(f"project: {project}")
        for ver in parsed_versions:
            print(f"({ver["date"]}) v {ver["version"]} : {ver["name"]} [blocks {len(ver["blocks"])}]")
            for block in ver["blocks"]:
                print(f"\t\tblock: {block["name"]} {"(pure-text)" if block["pure_text"] else ""}")
                for line in block["lines"]:
                    print(f"\t\t\t{line}")

    generate_pretty(project, parsed_versions, args.outdir)


if __name__ == "__main__":
    main(sys.argv)

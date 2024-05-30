#!/usr/bin/env python3
import argparse
import json
import os
import sys


# third-party imports


SCR_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCR_DIR)
# local chevron copy, make the import less hacky
import chevron


# Function and class definitions


def main(args):
    parser = argparse.ArgumentParser(prog="changelog.py")
    parser.add_argument("changelog")
    parser.add_argument("outdir")
    args = parser.parse_args()
    # https://github.com/noahmorrison/chevron
    # https://docs.python.org/3/library/argparse.html
    print(chevron.render("Hello, {{ mustache }}!", {"mustache": "World"}))


if __name__ == "__main__":
    main(sys.argv)

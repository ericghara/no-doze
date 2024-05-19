#!/bin/python3

import logging
import tempfile
import os
import os.path
import subprocess
from typing import *

LOG_LEVEL = "INFO"

REPO = "https://github.com/ericghara/no-doze.git"
# Used to construct archive names
ARCHIVE_PREFIX = "no-doze"
# Root directory of expanded archive.  *NEEDS* trailing slash
ARCHIVE_ROOT_DIR = "no-doze/"


def clone(temp_dir: str) -> None:
    logging.info(f"Cloning {REPO} into {temp_dir}")
    result = subprocess.run(["git", "clone", REPO, temp_dir], capture_output=True, text=True)
    if result.returncode != 0:
        logging.info(result.stdout)
        logging.info(result.stderr)
        logging.error("Unable to clone repo.")
        exit(-1)


def archive(temp_dir: str, commit_hash: str, version: str) -> None:
    tar_name = f"{ARCHIVE_PREFIX}-{version}.tar.gz"
    zip_name = f"{ARCHIVE_PREFIX}-{version}.zip"

    for archive_name in tar_name, zip_name:
        archive_path = os.path.join(os.getcwd(), archive_name)
        result = subprocess.run(["git", "-C", temp_dir, "archive", "-v", "-o", archive_path,
                                 f"--prefix={ARCHIVE_ROOT_DIR}", commit_hash], capture_output=True, text=True)
        if result.returncode != 0:
            logging.info(result.stdout)
            logging.info(result.stderr)
            logging.error(f"Unable to create archive: .", archive_name)
            exit(-1)

        logging.info(f"Successfully created release archive: {archive_path}")


if __name__ == "__main__":
    logging.basicConfig(level=LOG_LEVEL)

    commit_hash = input("Commit Hash to snapshot: ")
    if not hash:
        logging.error("Empty hash")
        exit(-1)

    version = input("Version number (i.e. 1.1): ").lower()
    if not version:
        logging.error("Empty version")
        exit(-1)

    if not version.startswith("v"):
        version = "v"+version

    with tempfile.TemporaryDirectory(prefix="no-doze-release") as temp_dir:
        clone(temp_dir=temp_dir)
        archive(temp_dir=temp_dir, commit_hash=commit_hash, version=version)

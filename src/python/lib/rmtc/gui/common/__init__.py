# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

import os
from pathlib import Path

ICON_SIZE = 100
SPACING = 300
DIALOG_SIZE = [500, 100]
RMTC_ICON_PATHS = f"{os.getenv('RMTC_RESOURCES')}/icons"


def get_icon_path(name, ext="svg"):
    paths = RMTC_ICON_PATHS.split(":")
    icon = Path(f"{name}.{ext}".lower())
    for path in paths:
        filename = Path(path) / icon
        if filename.exists():
            return str(filename)
    return None

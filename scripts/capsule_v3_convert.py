#!/usr/bin/env python3
from __future__ import annotations

import sys

import capsule_package_convert as _impl


if __name__ == "__main__":
    _impl.main()
else:
    sys.modules[__name__] = _impl

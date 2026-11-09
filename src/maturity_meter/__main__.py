"""Executable module for ``python -m maturity_meter``.

Python runs this file when the package is executed as a module. The real entry
logic lives in ``main.py`` so it can also be imported and tested directly.
"""

from maturity_meter.main import main

if __name__ == "__main__":
    main()

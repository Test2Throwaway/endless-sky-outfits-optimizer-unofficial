import sys

from .cli import main

if __name__ == "__main__":      # worker processes (spawn) import this module again; they must not run the CLI
    sys.exit(main())

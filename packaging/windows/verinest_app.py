"""Entry point for the frozen Windows build (PyInstaller)."""
import multiprocessing

from verinest.__main__ import main

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()

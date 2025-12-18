import pathlib
from py2app.build_app import py2app as _py2app
from setuptools import find_packages, setup

# Entry script for the macOS app bundle
APP = ["src/granola/menubar/app.py"]
DATA_FILES: list[str] = []

# Basic metadata
ROOT = pathlib.Path(__file__).parent
VERSION = "0.2.0"

# py2app options to build a self-contained menu bar app
OPTIONS = {
    # Do not show a Dock icon; run as agent-only menu bar app
    "plist": {
        "CFBundleName": "Wholesail Manager",
        "CFBundleDisplayName": "Wholesail Manager",
        "CFBundleIdentifier": "com.wholesail.manager",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSUIElement": True,
        # Apple Events permission prompt justification (used for folder pickers)
        "NSAppleEventsUsageDescription": "Wholesail Manager uses AppleScript to show folder pickers and manage settings.",
    },
    # Packages to make sure get included in the bundle
    "packages": [
        "granola",
        "certifi",
    ],
    # Libraries/modules to include explicitly
    "includes": [
        "rumps",
        "httpx",
        "yaml",
        "dotenv",
        "pydantic",
        "pydantic_settings",
        "certifi",
    ],
    # Finder/app bundle icon (generated via scripts/make_icns.sh)
    "iconfile": "macos/Wholesail.icns",
    # Build a standalone app that bundles Python and deps
    "argv_emulation": False,
}


class Py2AppCommand(_py2app):
    def finalize_options(self):  # type: ignore[override]
        # Py2app rejects install_requires; dependencies are pulled via imports/module graph.
        self.distribution.install_requires = []
        return super().finalize_options()


setup(
    app=APP,
    # Ensure the granola package and its assets are bundled
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        # Include the menubar icon so importlib.resources can load it
        "granola.menubar": ["assets/app_icon.png"],
    },
    include_package_data=True,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
    cmdclass={"py2app": Py2AppCommand},
)

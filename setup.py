"""Setup script for Switchback."""

from setuptools import setup, find_packages
from pathlib import Path

# Read version from package
version = {}
with open("switchback/__init__.py") as f:
    for line in f:
        if line.startswith("__version__"):
            exec(line, version)

# Read README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text() if readme_path.exists() else ""

setup(
    name="switchback",
    version=version["__version__"],
    author="Isaac",
    description="Solar-based dynamic wallpaper switcher for hyprpaper",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/switchback",  # Update with actual URL
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "astral>=3.2",
        "PyYAML>=6.0",
        "pytz>=2024.1",
        "Pillow>=10.0.0",
    ],
    extras_require={
        "gui": [
            "PyGObject>=3.48.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "switchback=switchback.main:cli",
        ],
        "gui_scripts": [
            "switchback-gui=switchback.gui.application:main",
        ],
    },
    data_files=[
        ("share/switchback", ["config.yaml"]),
        ("lib/systemd/user", ["switchback.service"]),
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Desktop Environment",
    ],
)

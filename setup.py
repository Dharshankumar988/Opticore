import os
from setuptools import find_packages, setup

long_description = ""
if os.path.exists("README.md"):
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()

setup(
    name="opticore-cli",
    version="1.2.0",
    author="OptiCore Vision Team",
    description="Cross-platform CLI Command Center for OptiCore Assistive Vision API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Environment :: Console",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28.0",
        "rich>=13.0.0",
        "pyttsx3>=2.90",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "fastapi>=0.100.0",
            "uvicorn>=0.20.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "opticore-cli=opticore_cli.cli:main",
        ],
    },
)

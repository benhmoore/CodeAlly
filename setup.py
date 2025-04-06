import os
import re
from setuptools import find_packages, setup

# Base directory
this_directory = os.path.abspath(os.path.dirname(__file__))

# Read the contents of README file
with open(os.path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()


# Function to read requirements files
def read_requirements(filename):
    with open(os.path.join(this_directory, filename), encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


# Function to extract metadata from __init__.py
def get_meta(meta_name):
    with open(os.path.join(this_directory, "code_ally", "__init__.py")) as f:
        meta_match = re.search(
            r"^__{meta}__ = ['\"]([^'\"]*)['\"]".format(meta=meta_name), f.read(), re.M
        )
    if meta_match:
        return meta_match.group(1)
    raise RuntimeError("Unable to find __{meta}__ string.".format(meta=meta_name))


# Get requirements
install_requires = read_requirements("requirements.txt")
dev_requires = read_requirements("requirements-dev.txt")

setup(
    name="code-ally",
    # Read version, author, email from code_ally/code_ally/__init__.py
    version=get_meta("version"),
    author=get_meta("author"),
    author_email=get_meta("email"),
    packages=find_packages(),
    install_requires=install_requires,
    extras_require={
        "dev": dev_requires,
    },
    entry_points={
        "console_scripts": [
            "ally=code_ally.main:main",
        ],
    },
    python_requires=">=3.8",
    description="A local LLM-powered pair programming assistant",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/benhmoore/code-ally",
    license="MIT",
    license_files=["LICENSE"],
    project_urls={
        "Bug Reports": "https://github.com/benhmoore/code-ally/issues",
        "Source": "https://github.com/benhmoore/code-ally",
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    keywords="llm, ai, pair programming, code assistant, development",
)

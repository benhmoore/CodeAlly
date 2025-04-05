import os

from setuptools import find_packages, setup

# Read the contents of README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()


# Read requirements files
def read_requirements(filename):
    with open(os.path.join(this_directory, filename), encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


install_requires = read_requirements("requirements.txt")
dev_requires = read_requirements("requirements-dev.txt")

setup(
    name="code-ally",
    version="0.3.4",
    packages=find_packages(),
    install_requires=install_requires,
    extras_require={
        "dev": dev_requires,
    },
    entry_points={
        "console_scripts": [
            "code-ally=code_ally.main:main",
        ],
    },
    python_requires=">=3.8",
    author="Ben H Moore",
    author_email="ben@benhmoore.com",
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
        "Topic :: Software Development",  # Changed from invalid classifier
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

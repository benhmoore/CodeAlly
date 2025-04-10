# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive test suite for all critical components
- GitHub Actions workflows for tests and linting
- CLI tests for basic functionality
- Version management with bump2version
- Automated release workflow for publishing to PyPI

### Changed
- Fixed circular import in task_planner.py
- Enhanced project structure to better follow Python best practices

### Fixed
- Circular dependencies in the code base

## [0.4.2] - 2023-04-06

### Added
- Directory tree generation for better project context
- Configurable depth and file limits for directory trees
- Integration with .gitignore for file exclusion

### Changed
- Improved system message with directory structure information
- Enhanced token usage efficiency

## [0.4.1] - 2023-03-15

### Added
- Support for Python 3.13
- Compatibility with newer LLMs

### Fixed
- Token estimation for large files
- Context window management improvements

## [0.4.0] - 2023-02-20

### Added
- Multi-step planning capability
- Enhanced error handling
- Improved tool response formatting

### Changed
- Updated prompt templates for better results
- Refactored tool manager for better performance
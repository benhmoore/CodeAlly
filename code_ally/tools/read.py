import os
import re
from typing import Any, Dict, List, Tuple, Optional

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool


@register_tool
class FileReadTool(BaseTool):
    name = "file_read"
    description = """Read the contents of a file with context-efficient options.
    
    Supports:
    - Reading specific line ranges (start_line, max_lines)
    - Searching for patterns with context (search_pattern, context_lines)
    - Reading sections based on delimiters (from_delimiter, to_delimiter)
    - Finding sections by headings or markers (section_pattern)
    """
    requires_confirmation = False

    def execute(
        self,
        path: str,
        start_line: int = 0,
        max_lines: int = 0,
        search_pattern: str = "",
        context_lines: int = 3,
        from_delimiter: str = "",
        to_delimiter: str = "",
        section_pattern: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Read the contents of a file with options to target specific sections or search results.

        Args:
            path: The path to the file to read
            start_line: Line number to start reading from (0-based, default: 0)
            max_lines: Maximum number of lines to read (0 for all, default: 0)
            search_pattern: Optional pattern to search within the file
            context_lines: Number of lines before/after matches to include (default: 3)
            from_delimiter: Start reading from this delimiter pattern (e.g., "# Section 1")
            to_delimiter: Stop reading at this delimiter pattern
            section_pattern: Extract sections matching this pattern (e.g., "## [\\w\\s]+")
            **kwargs: Additional arguments (unused)

        Returns:
            Dict with keys:
                success: Whether the file was read successfully
                content: The file's contents or matching sections
                line_count: Total number of lines in the file
                read_lines: Number of lines that were read
                file_size: Size of the file in bytes
                is_partial: Whether the content is a partial view
                is_binary: Whether the file appears to be binary
                error: Error message if any
        """
        try:
            # Expand user home directory if present
            file_path = os.path.expanduser(path)

            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "content": "",
                    "line_count": 0,
                    "read_lines": 0,
                    "file_size": 0,
                    "is_partial": False,
                    "is_binary": False,
                    "error": f"File not found: {file_path}",
                }

            if not os.path.isfile(file_path):
                return {
                    "success": False,
                    "content": "",
                    "line_count": 0,
                    "read_lines": 0,
                    "file_size": 0,
                    "is_partial": False,
                    "is_binary": False,
                    "error": f"Path is not a file: {file_path}",
                }

            # Get file size
            file_size = os.path.getsize(file_path)

            # Check if file might be binary
            is_binary = self._is_binary_file(file_path)
            if is_binary:
                return {
                    "success": True,
                    "content": "[Binary file]",
                    "line_count": 0,
                    "read_lines": 0,
                    "file_size": file_size,
                    "is_partial": True,
                    "is_binary": True,
                    "error": "",
                }

            # If delimiters are provided, use those for reading
            if from_delimiter or to_delimiter:
                content, lines_read, total_lines = self._read_with_delimiters(
                    file_path, from_delimiter, to_delimiter
                )
                is_partial = lines_read < total_lines

            # If section pattern is provided, extract matching sections
            elif section_pattern:
                content, sections_found, total_lines = self._read_sections(
                    file_path, section_pattern
                )
                lines_read = sections_found if sections_found > 0 else 0
                is_partial = True  # Section extraction is always partial

            # If search pattern is provided, use search reading
            elif search_pattern:
                content, matches, total_lines = self._read_with_pattern(
                    file_path, search_pattern, context_lines, start_line, max_lines
                )
                read_lines = len(matches) if matches else 0
                is_partial = read_lines < total_lines

            # Otherwise use standard line-based reading
            else:
                content, lines_read, total_lines = self._read_with_limits(
                    file_path, start_line, max_lines
                )
                is_partial = lines_read < total_lines

            return {
                "success": True,
                "content": content,
                "line_count": total_lines,
                "read_lines": lines_read if "lines_read" in locals() else 0,
                "file_size": file_size,
                "is_partial": is_partial,
                "is_binary": False,
                "error": "",
            }
        except Exception as exc:
            return {
                "success": False,
                "content": "",
                "line_count": 0,
                "read_lines": 0,
                "file_size": 0,
                "is_partial": False,
                "is_binary": False,
                "error": str(exc),
            }

    def _is_binary_file(self, file_path: str) -> bool:
        """Check if a file appears to be binary.

        Args:
            file_path: Path to the file

        Returns:
            True if the file appears to be binary, False otherwise
        """
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                return b"\0" in chunk  # Simple heuristic: contains null bytes
        except Exception:
            return False

    def _count_lines(self, file_path: str) -> int:
        """Count lines in a file efficiently.

        Args:
            file_path: Path to the file

        Returns:
            Number of lines in the file
        """
        lines = 0
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            # Use buffer read and count newlines for efficiency
            buf_size = 1024 * 1024
            read_f = f.read
            buf = read_f(buf_size)
            while buf:
                lines += buf.count("\n")
                buf = read_f(buf_size)
        return lines

    def _read_with_limits(
        self, file_path: str, start_line: int, max_lines: int
    ) -> Tuple[str, int, int]:
        """Read a file with line limits.

        Args:
            file_path: Path to the file
            start_line: Line to start reading from (0-based)
            max_lines: Maximum number of lines to read

        Returns:
            Tuple of (content, lines_read, total_lines)
        """
        content = []
        current_line = 0
        lines_read = 0

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if current_line >= start_line:
                    if max_lines > 0 and lines_read >= max_lines:
                        break
                    content.append(line.rstrip())
                    lines_read += 1
                current_line += 1

        # Add indicators for partial content
        result = "\n".join(content)
        if start_line > 0:
            result = f"[...] (skipped {start_line} lines)\n" + result

        if max_lines > 0 and current_line > start_line + lines_read:
            result += "\n[...] (more lines not shown)"

        return result, lines_read, current_line

    def _read_with_delimiters(
        self, file_path: str, from_delimiter: str, to_delimiter: str
    ) -> Tuple[str, int, int]:
        """Read a file between specified delimiters.

        Args:
            file_path: Path to the file
            from_delimiter: Start reading from this pattern
            to_delimiter: Stop reading at this pattern

        Returns:
            Tuple of (content, lines_read, total_lines)
        """
        content = []
        total_lines = 0
        lines_read = 0
        in_section = (
            from_delimiter == ""
        )  # If no start delimiter, start capturing immediately

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                total_lines += 1

                # Check for start delimiter if we're not already in a section
                if not in_section and from_delimiter and from_delimiter in line:
                    in_section = True
                    content.append(line.rstrip())
                    lines_read += 1
                    continue

                # If we're in a section, capture the line
                if in_section:
                    # Check if we've reached the end delimiter
                    if to_delimiter and to_delimiter in line:
                        content.append(line.rstrip())
                        lines_read += 1
                        break

                    content.append(line.rstrip())
                    lines_read += 1

        # If we didn't find any section
        if not content:
            return (
                f"No content found between '{from_delimiter}' and '{to_delimiter}'",
                0,
                total_lines,
            )

        result = "\n".join(content)

        # Add indicators for partial content
        if lines_read < total_lines:
            result += "\n[...] (more lines not shown)"

        return result, lines_read, total_lines

    def _read_sections(
        self, file_path: str, section_pattern: str
    ) -> Tuple[str, int, int]:
        """Extract sections matching a pattern from a file.

        Args:
            file_path: Path to the file
            section_pattern: Regex pattern that identifies section headers

        Returns:
            Tuple of (content, sections_found, total_lines)
        """
        try:
            section_regex = re.compile(section_pattern)
        except re.error:
            return f"Invalid regex pattern: {section_pattern}", 0, 0

        content = []
        total_lines = 0
        sections_found = 0
        current_section = []
        in_section = False

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                total_lines += 1

                # Check if this line is a section header
                if section_regex.search(line):
                    # If we were already in a section, save it
                    if in_section and current_section:
                        content.extend(current_section)
                        content.append("")  # Add a blank line between sections

                    # Start a new section
                    current_section = [line.rstrip()]
                    in_section = True
                    sections_found += 1
                elif in_section:
                    current_section.append(line.rstrip())

        # Add the last section if we have one
        if in_section and current_section:
            content.extend(current_section)

        if not content:
            return f"No sections matching '{section_pattern}' found", 0, total_lines

        return "\n".join(content), sections_found, total_lines

    def _read_with_pattern(
        self,
        file_path: str,
        pattern: str,
        context_lines: int,
        start_line: int,
        max_lines: int,
    ) -> Tuple[str, List[int], int]:
        """Read a file and extract sections matching a pattern.

        Args:
            file_path: Path to the file
            pattern: Pattern to search for
            context_lines: Number of context lines around matches
            start_line: Line to start reading from
            max_lines: Maximum matches to include (0 for all)

        Returns:
            Tuple of (content, matching_line_numbers, total_lines)
        """
        import re  # pylint: disable=import-outside-toplevel

        try:
            pattern_re = re.compile(pattern)
        except re.error:
            # Fall back to basic string search if regex is invalid
            pattern_re = None

        matches = []
        context_blocks = []
        total_lines = 0
        match_count = 0

        # First pass: find matching lines
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = []
            for i, line in enumerate(f):
                if i < start_line:
                    continue

                lines.append(line.rstrip())
                total_lines = i + 1

                # Check for pattern match
                if pattern_re and pattern_re.search(line):
                    matches.append(i)
                    match_count += 1
                elif pattern_re is None and pattern in line:
                    matches.append(i)
                    match_count += 1

                # Stop if we've reached max matches
                if max_lines > 0 and match_count >= max_lines:
                    break

        # No matches found
        if not matches:
            return f"No matches found for pattern: {pattern}", [], total_lines

        # Second pass: build context blocks
        for match_line in matches:
            start = max(0, match_line - context_lines)
            end = min(len(lines) - 1, match_line + context_lines)

            # Add separator between non-contiguous blocks
            if context_blocks and start > context_blocks[-1][1] + 1:
                context_blocks.append((-1, -1))  # Sentinel for separator

            # Add this block or extend previous block
            if not context_blocks or start > context_blocks[-1][1]:
                context_blocks.append((start, end))
            else:
                # Extend previous block
                context_blocks[-1] = (context_blocks[-1][0], end)

        # Build final content with appropriate separators and line numbers
        result = []
        for _, (start, end) in enumerate(context_blocks):
            if start == -1:  # Sentinel for separator
                result.append("\n[...] (skipped lines)\n")
                continue

            block_lines = []
            for j in range(start, end + 1):
                line_num = j + 1  # Convert to 1-based numbering for display
                if j in matches:
                    block_lines.append(f"{line_num}: >> {lines[j]}")
                else:
                    block_lines.append(f"{line_num}:    {lines[j]}")

            result.append("\n".join(block_lines))

        return "\n".join(result), matches, total_lines

import os
import re
import ast
import json
from typing import Any, Dict, List, Set, Tuple, Optional, Union

from code_ally.tools.base import BaseTool
from code_ally.tools.registry import register_tool


@register_tool
class CodeStructureAnalyzerTool(BaseTool):
    name = "code_structure"
    description = """Analyze code structure in files or directories.
    
    Supports:
    - Function/method analysis (signatures, docstrings)
    - Class hierarchy and relationships
    - Import/dependency analysis
    - Module structure overview
    - Multiple programming languages (Python, JavaScript, TypeScript, etc.)
    """
    requires_confirmation = False

    # Languages that can be analyzed
    SUPPORTED_LANGUAGES = {
        "python": [".py"],
        "javascript": [".js", ".jsx"],
        "typescript": [".ts", ".tsx"],
        "java": [".java"],
        "c": [".c", ".h"],
        "cpp": [".cpp", ".hpp", ".cc", ".hh"],
        "go": [".go"],
        "ruby": [".rb"],
        "php": [".php"],
        "csharp": [".cs"],
    }

    def execute(
        self,
        path: str,
        language: str = "",
        include_functions: bool = True,
        include_classes: bool = True,
        include_imports: bool = True,
        include_dependencies: bool = False,
        recursive: bool = False,
        exclude_dirs: str = "",
        max_files: int = 50,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Analyze code structure in files or directories.

        Args:
            path: The path to the file or directory to analyze
            language: Programming language to analyze (auto-detected if not specified)
            include_functions: Whether to include function/method analysis
            include_classes: Whether to include class analysis
            include_imports: Whether to include import/module analysis
            include_dependencies: Whether to analyze dependencies between files
            recursive: Whether to analyze directories recursively
            exclude_dirs: Comma-separated list of directories to exclude (e.g., "node_modules,venv")
            max_files: Maximum number of files to analyze
            **kwargs: Additional arguments (unused)

        Returns:
            Dict with keys:
                success: Whether the analysis was successful
                error: Error message if any
                structure: The analyzed code structure
                files_analyzed: List of files that were analyzed
                language: Detected language
        """
        try:
            # Expand user home directory if present
            file_path = os.path.expanduser(path)

            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "error": f"Path not found: {file_path}",
                    "structure": {},
                    "files_analyzed": [],
                    "language": "",
                }

            # Determine what files to analyze
            files_to_analyze = []

            # Parse exclude directories
            excluded_directories = [
                d.strip() for d in exclude_dirs.split(",") if d.strip()
            ]

            if os.path.isfile(file_path):
                # Single file analysis
                files_to_analyze.append(file_path)
                # Auto-detect language if not provided
                if not language:
                    language = self._detect_language(file_path)
            else:
                # Directory analysis
                language_exts = []
                if language:
                    # Get extensions for specified language
                    language_exts = self.SUPPORTED_LANGUAGES.get(language.lower(), [])

                # Collect files
                files_to_analyze = self._collect_files(
                    file_path, language_exts, recursive, excluded_directories, max_files
                )

                if not files_to_analyze:
                    if language:
                        return {
                            "success": False,
                            "error": f"No {language} files found in {file_path}",
                            "structure": {},
                            "files_analyzed": [],
                            "language": language,
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"No supported code files found in {file_path}",
                            "structure": {},
                            "files_analyzed": [],
                            "language": "",
                        }

                # Auto-detect language if not provided
                if not language:
                    language = self._detect_language(files_to_analyze[0])

            # Analyze the files
            structure = {}
            successfully_analyzed = []

            for file in files_to_analyze:
                try:
                    # Select the appropriate analyzer based on language
                    if language.lower() == "python":
                        file_structure = self._analyze_python_file(
                            file, include_functions, include_classes, include_imports
                        )
                    elif language.lower() in ["javascript", "typescript"]:
                        file_structure = self._analyze_js_ts_file(
                            file, include_functions, include_classes, include_imports
                        )
                    else:
                        # Generic analyzer for other languages
                        file_structure = self._analyze_generic_file(
                            file,
                            language,
                            include_functions,
                            include_classes,
                            include_imports,
                        )

                    if file_structure:
                        rel_path = (
                            os.path.relpath(file, file_path)
                            if os.path.isdir(file_path)
                            else os.path.basename(file)
                        )
                        structure[rel_path] = file_structure
                        successfully_analyzed.append(file)
                except Exception as e:
                    # Skip files that can't be analyzed
                    continue

            # Analyze dependencies between files if requested
            if include_dependencies and len(successfully_analyzed) > 1:
                dependencies = self._analyze_dependencies(
                    successfully_analyzed, language, structure
                )
                structure["__dependencies__"] = dependencies

            # Generate overall summary
            structure["__summary__"] = self._generate_summary(structure, language)

            return {
                "success": True,
                "error": "",
                "structure": structure,
                "files_analyzed": successfully_analyzed,
                "language": language,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "structure": {},
                "files_analyzed": [],
                "language": language if "language" in locals() else "",
            }

    def _collect_files(
        self,
        directory: str,
        extensions: List[str],
        recursive: bool,
        excluded_dirs: List[str],
        max_files: int,
    ) -> List[str]:
        """Collect files matching the given extensions.

        Args:
            directory: Directory to search in
            extensions: List of file extensions to include
            recursive: Whether to search recursively
            excluded_dirs: List of directories to exclude
            max_files: Maximum number of files to collect

        Returns:
            List of matching file paths
        """
        files = []

        # If no extensions provided, use all supported extensions
        if not extensions:
            extensions = []
            for exts in self.SUPPORTED_LANGUAGES.values():
                extensions.extend(exts)

        # Handle recursive vs. non-recursive collection
        if recursive:
            for root, dirs, filenames in os.walk(directory):
                # Skip excluded directories
                dirs[:] = [d for d in dirs if d not in excluded_dirs]

                for filename in filenames:
                    # Check if the file has a supported extension
                    if any(filename.endswith(ext) for ext in extensions):
                        files.append(os.path.join(root, filename))

                        # Check if we've reached the maximum
                        if len(files) >= max_files:
                            return files
        else:
            # Non-recursive - just check files in the directory
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                if os.path.isfile(filepath) and any(
                    filename.endswith(ext) for ext in extensions
                ):
                    files.append(filepath)

                    # Check if we've reached the maximum
                    if len(files) >= max_files:
                        break

        return files

    def _detect_language(self, file_path: str) -> str:
        """Detect the programming language based on file extension.

        Args:
            file_path: Path to the file

        Returns:
            Detected language name
        """
        _, ext = os.path.splitext(file_path)

        for language, extensions in self.SUPPORTED_LANGUAGES.items():
            if ext in extensions:
                return language

        # Default to generic analysis if language can't be detected
        return "generic"

    def _analyze_python_file(
        self,
        file_path: str,
        include_functions: bool,
        include_classes: bool,
        include_imports: bool,
    ) -> Dict[str, Any]:
        """Analyze a Python file using the ast module.

        Args:
            file_path: Path to the Python file
            include_functions: Whether to include function analysis
            include_classes: Whether to include class analysis
            include_imports: Whether to include import analysis

        Returns:
            Dict with analysis results
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse the Python code
            tree = ast.parse(content)

            result = {}

            # Analyze imports
            if include_imports:
                imports = []

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            imports.append({"name": name.name, "asname": name.asname})
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        for name in node.names:
                            imports.append(
                                {
                                    "name": (
                                        f"{module}.{name.name}" if module else name.name
                                    ),
                                    "asname": name.asname,
                                    "from_import": True,
                                    "module": module,
                                }
                            )

                result["imports"] = imports

            # Analyze functions
            if include_functions:
                functions = []

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) or isinstance(
                        node, ast.AsyncFunctionDef
                    ):
                        # Skip methods (they'll be included in class analysis)
                        if not include_classes or not any(
                            isinstance(parent, ast.ClassDef)
                            for parent in ast.iter_child_nodes(tree)
                            if hasattr(parent, "body") and node in parent.body
                        ):
                            func_info = {
                                "name": node.name,
                                "async": isinstance(node, ast.AsyncFunctionDef),
                                "decorators": [
                                    self._get_decorator_name(d)
                                    for d in node.decorator_list
                                ],
                                "args": self._get_function_args(node),
                                "returns": self._get_return_annotation(node),
                                "docstring": ast.get_docstring(node) or "",
                                "line": node.lineno,
                            }
                            functions.append(func_info)

                result["functions"] = functions

            # Analyze classes
            if include_classes:
                classes = []

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        class_info = {
                            "name": node.name,
                            "bases": [self._get_base_name(base) for base in node.bases],
                            "decorators": [
                                self._get_decorator_name(d) for d in node.decorator_list
                            ],
                            "docstring": ast.get_docstring(node) or "",
                            "line": node.lineno,
                            "methods": [],
                            "class_variables": [],
                        }

                        # Analyze methods and class variables
                        for child in node.body:
                            if isinstance(child, ast.FunctionDef) or isinstance(
                                child, ast.AsyncFunctionDef
                            ):
                                method_info = {
                                    "name": child.name,
                                    "async": isinstance(child, ast.AsyncFunctionDef),
                                    "decorators": [
                                        self._get_decorator_name(d)
                                        for d in child.decorator_list
                                    ],
                                    "args": self._get_function_args(child),
                                    "returns": self._get_return_annotation(child),
                                    "docstring": ast.get_docstring(child) or "",
                                    "line": child.lineno,
                                }
                                class_info["methods"].append(method_info)
                            elif isinstance(child, ast.Assign) and all(
                                isinstance(target, ast.Name) for target in child.targets
                            ):
                                for target in child.targets:
                                    class_info["class_variables"].append(
                                        {"name": target.id, "line": child.lineno}
                                    )

                        classes.append(class_info)

                result["classes"] = classes

            return result
        except Exception as e:
            return {"error": f"Failed to analyze Python file: {str(e)}"}

    def _get_function_args(self, node: ast.FunctionDef) -> List[Dict[str, str]]:
        """Extract function arguments from a FunctionDef node.

        Args:
            node: The FunctionDef node

        Returns:
            List of argument information
        """
        args = []

        for arg in node.args.args:
            arg_info = {"name": arg.arg, "annotation": ""}

            if arg.annotation:
                arg_info["annotation"] = self._get_annotation_name(arg.annotation)

            args.append(arg_info)

        # Handle keyword arguments
        if node.args.kwarg:
            args.append(
                {
                    "name": f"**{node.args.kwarg.arg}",
                    "annotation": (
                        self._get_annotation_name(node.args.kwarg.annotation)
                        if node.args.kwarg.annotation
                        else ""
                    ),
                }
            )

        # Handle varargs
        if node.args.vararg:
            args.append(
                {
                    "name": f"*{node.args.vararg.arg}",
                    "annotation": (
                        self._get_annotation_name(node.args.vararg.annotation)
                        if node.args.vararg.annotation
                        else ""
                    ),
                }
            )

        return args

    def _get_annotation_name(self, annotation: ast.AST) -> str:
        """Convert an annotation AST node to a string.

        Args:
            annotation: The annotation AST node

        Returns:
            String representation of the annotation
        """
        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Attribute):
            return f"{self._get_annotation_name(annotation.value)}.{annotation.attr}"
        elif isinstance(annotation, ast.Subscript):
            return f"{self._get_annotation_name(annotation.value)}[{self._get_annotation_name(annotation.slice)}]"
        elif isinstance(annotation, ast.Index):
            return self._get_annotation_name(annotation.value)
        elif isinstance(annotation, ast.Tuple):
            return ", ".join(self._get_annotation_name(elt) for elt in annotation.elts)
        elif isinstance(annotation, ast.Constant):
            return str(annotation.value)
        else:
            return "..."  # For complex annotations

    def _get_return_annotation(self, node: ast.FunctionDef) -> str:
        """Get the return annotation of a function.

        Args:
            node: The FunctionDef node

        Returns:
            String representation of the return annotation
        """
        if node.returns:
            return self._get_annotation_name(node.returns)
        return ""

    def _get_base_name(self, base: ast.AST) -> str:
        """Convert a base class AST node to a string.

        Args:
            base: The base class AST node

        Returns:
            String representation of the base class
        """
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            return f"{self._get_base_name(base.value)}.{base.attr}"
        else:
            return "..."  # For complex base classes

    def _get_decorator_name(self, decorator: ast.AST) -> str:
        """Convert a decorator AST node to a string.

        Args:
            decorator: The decorator AST node

        Returns:
            String representation of the decorator
        """
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return f"{self._get_decorator_name(decorator.value)}.{decorator.attr}"
        elif isinstance(decorator, ast.Call):
            return f"{self._get_decorator_name(decorator.func)}(...)"
        else:
            return "..."  # For complex decorators

    def _analyze_js_ts_file(
        self,
        file_path: str,
        include_functions: bool,
        include_classes: bool,
        include_imports: bool,
    ) -> Dict[str, Any]:
        """Analyze a JavaScript/TypeScript file using regex patterns.

        Args:
            file_path: Path to the JavaScript/TypeScript file
            include_functions: Whether to include function analysis
            include_classes: Whether to include class analysis
            include_imports: Whether to include import analysis

        Returns:
            Dict with analysis results
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            result = {}

            # Analyze imports
            if include_imports:
                imports = []

                # ES6 import statements
                import_pattern = (
                    r'import\s+(?:(\{[^}]+\})|([^{;]+?))\s+from\s+[\'"]([^\'"]+)[\'"]'
                )
                for match in re.finditer(import_pattern, content):
                    named_imports, default_import, module = match.groups()

                    if default_import and default_import.strip():
                        imports.append(
                            {
                                "name": default_import.strip(),
                                "module": module,
                                "type": "default",
                            }
                        )

                    if named_imports:
                        # Extract individual named imports
                        for named_import in re.finditer(
                            r"([^,{\s]+)(?:\s+as\s+([^,}\s]+))?", named_imports
                        ):
                            original, alias = named_import.groups()
                            imports.append(
                                {
                                    "name": original.strip(),
                                    "asname": alias.strip() if alias else None,
                                    "module": module,
                                    "type": "named",
                                }
                            )

                # CommonJS require statements
                require_pattern = r'(?:const|let|var)\s+(?:(\{[^}]+\})|([^{;=]+))\s*=\s*require\([\'"]([^\'"]+)[\'"]\)'
                for match in re.finditer(require_pattern, content):
                    named_imports, variable_name, module = match.groups()

                    if variable_name and variable_name.strip():
                        imports.append(
                            {
                                "name": variable_name.strip(),
                                "module": module,
                                "type": "require",
                            }
                        )

                    if named_imports:
                        # Extract individual named imports
                        for named_import in re.finditer(
                            r"([^,{\s]+)(?:\s*:\s*([^,}\s]+))?", named_imports
                        ):
                            original, alias = named_import.groups()
                            imports.append(
                                {
                                    "name": original.strip(),
                                    "asname": alias.strip() if alias else None,
                                    "module": module,
                                    "type": "require-destructured",
                                }
                            )

                result["imports"] = imports

            # Analyze functions
            if include_functions:
                functions = []

                # Function declarations
                function_pattern = r"(?:async\s+)?function\s+([^(]+)\s*\(([^)]*)\)\s*(?::\s*([^{]+))?\s*\{"
                for match in re.finditer(function_pattern, content):
                    name, params, return_type = match.groups()

                    # Extract docstring (JSDoc comment)
                    docstring = ""
                    pos = match.start()
                    jsdoc_match = re.search(r"/\*\*([\s\S]*?)\*/", content[:pos])
                    if jsdoc_match and not re.search(
                        r"[^\s]", content[jsdoc_match.end() : pos]
                    ):
                        docstring = jsdoc_match.group(1).strip()

                    functions.append(
                        {
                            "name": name.strip(),
                            "params": (
                                [p.strip() for p in params.split(",")] if params else []
                            ),
                            "return_type": return_type.strip() if return_type else "",
                            "async": "async" in match.group(0),
                            "docstring": docstring,
                            "line": content[: match.start()].count("\n") + 1,
                        }
                    )

                # Arrow functions with explicit names (const/let/var assignments)
                arrow_pattern = r"(?:const|let|var)\s+([^=]+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*(?::\s*([^=]+))?\s*=>"
                for match in re.finditer(arrow_pattern, content):
                    name, params, return_type = match.groups()

                    # Extract docstring (JSDoc comment)
                    docstring = ""
                    pos = match.start()
                    jsdoc_match = re.search(r"/\*\*([\s\S]*?)\*/", content[:pos])
                    if jsdoc_match and not re.search(
                        r"[^\s]", content[jsdoc_match.end() : pos]
                    ):
                        docstring = jsdoc_match.group(1).strip()

                    functions.append(
                        {
                            "name": name.strip(),
                            "params": (
                                [p.strip() for p in params.split(",")] if params else []
                            ),
                            "return_type": return_type.strip() if return_type else "",
                            "async": "async" in match.group(0),
                            "is_arrow": True,
                            "docstring": docstring,
                            "line": content[: match.start()].count("\n") + 1,
                        }
                    )

                result["functions"] = functions

            # Analyze classes
            if include_classes:
                classes = []

                # Class declarations
                class_pattern = r"class\s+([^{\s]+)(?:\s+extends\s+([^{\s]+))?\s*\{"
                for match in re.finditer(class_pattern, content):
                    class_name, base_class = match.groups()

                    # Extract docstring (JSDoc comment)
                    docstring = ""
                    pos = match.start()
                    jsdoc_match = re.search(r"/\*\*([\s\S]*?)\*/", content[:pos])
                    if jsdoc_match and not re.search(
                        r"[^\s]", content[jsdoc_match.end() : pos]
                    ):
                        docstring = jsdoc_match.group(1).strip()

                    # Find class body
                    class_start = content.find("{", match.end())
                    if class_start != -1:
                        # Find matching closing brace
                        depth = 1
                        class_end = class_start + 1
                        while depth > 0 and class_end < len(content):
                            if content[class_end] == "{":
                                depth += 1
                            elif content[class_end] == "}":
                                depth -= 1
                            class_end += 1

                        class_body = content[class_start:class_end]

                        # Extract methods
                        methods = []

                        # Constructor
                        constructor_pattern = r"constructor\s*\(([^)]*)\)\s*\{"
                        constructor_match = re.search(constructor_pattern, class_body)
                        if constructor_match:
                            params = constructor_match.group(1)
                            methods.append(
                                {
                                    "name": "constructor",
                                    "params": (
                                        [p.strip() for p in params.split(",")]
                                        if params
                                        else []
                                    ),
                                    "is_constructor": True,
                                }
                            )

                        # Regular methods
                        method_pattern = r"(?:async\s+)?(?:static\s+)?(?:get|set)?\s*([^(]+)\s*\(([^)]*)\)\s*(?::\s*([^{]+))?\s*\{"
                        for method_match in re.finditer(method_pattern, class_body):
                            method_name, params, return_type = method_match.groups()

                            # Skip constructor (already handled)
                            if method_name.strip() == "constructor":
                                continue

                            methods.append(
                                {
                                    "name": method_name.strip(),
                                    "params": (
                                        [p.strip() for p in params.split(",")]
                                        if params
                                        else []
                                    ),
                                    "return_type": (
                                        return_type.strip() if return_type else ""
                                    ),
                                    "static": "static" in method_match.group(0),
                                    "async": "async" in method_match.group(0),
                                    "getter": "get " in method_match.group(0),
                                    "setter": "set " in method_match.group(0),
                                }
                            )

                        # Class properties
                        properties = []
                        property_pattern = (
                            r"(?:static\s+)?([^=;\s(]+)\s*(?::\s*([^=;]+))?\s*=?"
                        )
                        for prop_match in re.finditer(property_pattern, class_body):
                            prop_name, prop_type = prop_match.groups()

                            # Skip methods (already handled)
                            method_names = [m["name"] for m in methods]
                            if prop_name.strip() in method_names:
                                continue

                            properties.append(
                                {
                                    "name": prop_name.strip(),
                                    "type": prop_type.strip() if prop_type else "",
                                    "static": "static" in prop_match.group(0),
                                }
                            )

                        classes.append(
                            {
                                "name": class_name.strip(),
                                "extends": base_class.strip() if base_class else "",
                                "methods": methods,
                                "properties": properties,
                                "docstring": docstring,
                                "line": content[: match.start()].count("\n") + 1,
                            }
                        )

                result["classes"] = classes

            return result
        except Exception as e:
            return {"error": f"Failed to analyze JavaScript/TypeScript file: {str(e)}"}

    def _analyze_generic_file(
        self,
        file_path: str,
        language: str,
        include_functions: bool,
        include_classes: bool,
        include_imports: bool,
    ) -> Dict[str, Any]:
        """Analyze a file in a language without specific support using regex patterns.

        Args:
            file_path: Path to the file
            language: Language of the file
            include_functions: Whether to include function analysis
            include_classes: Whether to include class analysis
            include_imports: Whether to include import analysis

        Returns:
            Dict with analysis results
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            result = {}

            # Count lines of code and identify structure based on indentation patterns
            lines = content.splitlines()
            result["total_lines"] = len(lines)
            result["non_blank_lines"] = sum(1 for line in lines if line.strip())

            # Simple comment detection (language-specific)
            comment_chars = {
                "generic": "//",
                "java": "//",
                "c": "//",
                "cpp": "//",
                "csharp": "//",
                "go": "//",
                "ruby": "#",
                "php": "//",
            }

            comment_char = comment_chars.get(language.lower(), "#")
            result["comment_lines"] = sum(
                1 for line in lines if line.strip().startswith(comment_char)
            )

            # Use simple regex patterns to detect common structures
            structures = []

            if include_functions:
                # Try to detect functions with basic patterns
                function_patterns = {
                    "java": r"(?:public|private|protected|static|\s) +[\w\<\>\[\]]+\s+(\w+) *\([^\)]*\) *(?:\{|throws|;)",
                    "c": r"\w+\s+(\w+)\s*\([^;]*\)\s*\{",
                    "cpp": r"(?:virtual |static )?[\w\<\>\[\]]+\s+(\w+)\s*\([^;]*\)\s*(?:const|override|final|noexcept)?\s*(?:\{|;)",
                    "csharp": r"(?:public|private|protected|static|internal|virtual|abstract|\s) +[\w\<\>\[\]]+\s+(\w+)\s*\([^\)]*\)\s*(?:\{|;)",
                    "go": r"func\s+(\w+)\s*\([^{]*\)\s*(?:\(.*\))?\s*\{",
                    "ruby": r"def\s+(\w+)(?:\(.*\))?\s*(?:\n|$)",
                    "php": r"function\s+(\w+)\s*\([^{]*\)\s*(?::\s*\w+)?\s*\{",
                }

                pattern = function_patterns.get(language.lower())
                if pattern:
                    for match in re.finditer(pattern, content, re.MULTILINE):
                        function_name = match.group(1)
                        structures.append(
                            {
                                "type": "function",
                                "name": function_name,
                                "line": content[: match.start()].count("\n") + 1,
                            }
                        )

            if include_classes:
                # Try to detect classes with basic patterns
                class_patterns = {
                    "java": r"(?:public|private|protected|abstract|\s) +(?:class|interface|enum)\s+(\w+)",
                    "cpp": r"(?:class|struct)\s+(\w+)(?:\s*:\s*(?:public|private|protected)\s+\w+)?",
                    "csharp": r"(?:public|private|protected|internal|abstract|\s) +(?:class|interface|enum|struct)\s+(\w+)",
                    "php": r"(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+\w+|\s+implements\s+(?:\w+(?:,\s*\w+)*))?",
                }

                pattern = class_patterns.get(language.lower())
                if pattern:
                    for match in re.finditer(pattern, content, re.MULTILINE):
                        class_name = match.group(1)
                        structures.append(
                            {
                                "type": "class",
                                "name": class_name,
                                "line": content[: match.start()].count("\n") + 1,
                            }
                        )

            if include_imports:
                # Try to detect imports with basic patterns
                import_patterns = {
                    "java": r"import\s+([\w\.]+)(?:\s*;\s*|$)",
                    "c": r'#include\s+[<"]([\w\.\/]+)[>"]',
                    "cpp": r'#include\s+[<"]([\w\.\/]+)[>"]',
                    "csharp": r"using\s+([\w\.]+)(?:\s*;\s*|$)",
                    "go": r"import\s+(?:\"([\w\.\/]+)\"|(?:\(\s*\"([\w\.\/]+)\"))",
                    "ruby": r"require\s+[\'\"]([\w\.\/]+)[\'\"]\s*(?:\n|$)",
                    "php": r"(?:require|include|require_once|include_once)\s+[\'\"]([\w\.\/]+)[\'\"]\s*;",
                }

                pattern = import_patterns.get(language.lower())
                if pattern:
                    imports = []
                    for match in re.finditer(pattern, content, re.MULTILINE):
                        import_name = (
                            match.group(1) if match.group(1) else match.group(2)
                        )
                        imports.append(
                            {
                                "name": import_name,
                                "line": content[: match.start()].count("\n") + 1,
                            }
                        )
                    result["imports"] = imports

            result["structures"] = structures

            return result
        except Exception as e:
            return {"error": f"Failed to analyze file: {str(e)}"}

    def _analyze_dependencies(
        self, files: List[str], language: str, structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze dependencies between files.

        Args:
            files: List of files to analyze
            language: Language of the files
            structure: Structure data from file analysis

        Returns:
            Dict with dependency information
        """
        dependencies = {"imports": {}, "exports": {}, "graph": {}}

        file_map = {}
        for file in files:
            file_key = os.path.basename(file)
            file_map[file_key] = file
            dependencies["imports"][file_key] = []
            dependencies["exports"][file_key] = []
            dependencies["graph"][file_key] = []

        # Analyze imports/exports for each file
        for file_key, file_struct in structure.items():
            if file_key.startswith("__"):  # Skip special keys
                continue

            # Check imports
            if "imports" in file_struct:
                for imp in file_struct["imports"]:
                    module_name = imp.get("module", imp.get("name", ""))

                    # If the module is one of our files (try to match)
                    for other_file in file_map:
                        # Check if the import points to this file
                        # This is a simplistic check; in a real implementation
                        # it would need to consider module resolution logic
                        if (
                            module_name.replace("/", ".")
                            .replace(".js", "")
                            .replace(".ts", "")
                            .replace(".py", "")
                            in other_file
                        ):
                            dependencies["imports"][file_key].append(other_file)
                            dependencies["graph"][file_key].append(other_file)
                            dependencies["exports"][other_file].append(file_key)

        return dependencies

    def _generate_summary(
        self, structure: Dict[str, Any], language: str
    ) -> Dict[str, Any]:
        """Generate a summary of the code structure.

        Args:
            structure: The analyzed code structure
            language: The programming language

        Returns:
            Dict with summary information
        """
        summary = {
            "language": language,
            "total_files": 0,
            "total_functions": 0,
            "total_classes": 0,
            "total_imports": 0,
            "total_lines": 0,
            "top_level_components": [],
        }

        for file_key, file_struct in structure.items():
            if file_key.startswith("__"):  # Skip special keys
                continue

            summary["total_files"] += 1

            # Count functions
            if "functions" in file_struct:
                summary["total_functions"] += len(file_struct["functions"])

            # Count classes
            if "classes" in file_struct:
                summary["total_classes"] += len(file_struct["classes"])

                # Add top-level classes to the components list
                for cls in file_struct["classes"]:
                    summary["top_level_components"].append(
                        {"type": "class", "name": cls["name"], "file": file_key}
                    )

            # Count imports
            if "imports" in file_struct:
                summary["total_imports"] += len(file_struct["imports"])

            # Count lines
            if "total_lines" in file_struct:
                summary["total_lines"] += file_struct["total_lines"]

            # Add top-level functions to the components list
            if "functions" in file_struct:
                for func in file_struct["functions"]:
                    # Only add top-level functions (not methods)
                    if "classes" not in file_struct or not any(
                        func["name"] in [m["name"] for m in cls.get("methods", [])]
                        for cls in file_struct["classes"]
                    ):
                        summary["top_level_components"].append(
                            {"type": "function", "name": func["name"], "file": file_key}
                        )

        return summary

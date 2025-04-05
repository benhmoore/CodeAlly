"""Search tools guidance for contextual help."""

SEARCH_GUIDANCE = """
ENHANCED SEARCH TOOLS GUIDANCE:

When searching through code and files, follow these expert techniques:

1. PATTERN MATCHING STRATEGY:
   - Start with broad patterns, then refine: first `config.*` then `config.*\\.json`
   - Use glob patterns for file name searches: `glob pattern="**/*.py"`
   - Use grep patterns for content searches: `grep pattern="function\\s+getName"`
   - Combine glob and grep for targeted searches: first find files, then search within them
   - Search incrementally, using results of one search to inform the next

2. EFFECTIVE GREP PATTERNS:
   - For function definitions: `function\\s+([a-zA-Z_][a-zA-Z0-9_]*)`
   - For method definitions: `def\\s+([a-zA-Z_][a-zA-Z0-9_]*)`
   - For variable assignments: `const\\s+([a-zA-Z_][a-zA-Z0-9_]*)\\s*=`
   - For imports/requires: `(import|require).*['\"']([^'\"']+)['\"']`
   - For class definitions: `class\\s+([a-zA-Z_][a-zA-Z0-9_]*)`
   - For API routes/endpoints: `(app|router)\\.(get|post|put|delete)\\(['\"']([^'\"']+)['\"']`

3. GLOB PATTERN TECHNIQUES:
   - Find all source files: `**/*.{js,ts,py,go,java,rb}`
   - Find configuration files: `**/{config,configuration}*.*`
   - Find test files: `**/test{s,}/**/*.{js,py,ts}` or `**/*{_,-}test.{js,py,ts}`
   - Find documentation: `**/{doc,docs,documentation}/**/*`
   - Exclude patterns: Use the `ignore` parameter with patterns like `**/node_modules/**`

4. SEARCH RESULT ANALYSIS:
   - Scan results for patterns and relationships
   - Look for interdependencies between files in search results
   - Identify common patterns or conventions in the codebase
   - Track search paths to understand directory structure
   - Note any outliers or exceptions to patterns

5. DISCOVERY WORKFLOWS:
   - For unknown codebases: First find entry points (main.py, index.js, etc.)
   - For feature searches: Look for UI components, then trace to handlers/controllers
   - For bug investigation: Search for error messages, exceptions, or related functions
   - For refactoring: Find all usages of a function/method/class before modifying it
   - For dependency analysis: Search for import/require statements

6. SEARCH OPTIMIZATION:
   - Limit search scope to relevant directories when possible
   - Use negative patterns to exclude noise: `grep -v "test" or --exclude=pattern`
   - For large codebases, search in stages (entry points → core modules → utilities)
   - When searching for specific code, include distinctive syntax or variable names
   - For multilingual codebases, search language by language

DETAILED EXAMPLES:

Example 1: Finding and analyzing a specific feature implementation
```
# First find potential entry points or main files
glob pattern="**/main.py" 
glob pattern="**/app.py"
glob pattern="**/index.js"

# Look for a feature-specific module or component
glob pattern="**/*user*.{py,js,ts}"

# Search for class or function definitions related to the feature
grep pattern="class\\s+User" include="*.py"
grep pattern="def\\s+create_user" include="*.py"
grep pattern="function\\s+createUser" include="*.{js,ts}"

# Find API endpoints related to the feature
grep pattern="@app.route\\(['\"']/users?['\"']" include="*.py"
grep pattern="router\\.(get|post|put|delete)\\(['\"']/users?['\"']" include="*.{js,ts}"

# Trace usage throughout the codebase
grep pattern="User\\(" include="*.py"
grep pattern="createUser\\(" include="*.{js,ts}"

# Find tests related to the feature
glob pattern="**/test_*user*.py"
glob pattern="**/*user*test.{js,ts}"
```

Example 2: Investigating a specific error or bug
```
# Search for error messages across the codebase
grep pattern="Authentication failed" include="*.{py,js,ts,log}"

# Look for exception handling related to the error
grep pattern="try\\s*:\\s*.*\\s*except\\s+AuthError" include="*.py"
grep pattern="try\\s*{.*}\\s*catch\\s*\\(AuthError" include="*.{js,ts}"

# Find where the error might be thrown
grep pattern="raise\\s+AuthError" include="*.py"
grep pattern="throw\\s+new\\s+AuthError" include="*.{js,ts}"

# Check configuration related to the feature
glob pattern="**/auth*config*.{json,yaml,py,js,ts}"

# Search for authentication-related functions or methods
grep pattern="def\\s+authenticate" include="*.py"
grep pattern="function\\s+authenticate" include="*.{js,ts}"
```

Example 3: Exploring an unfamiliar codebase
```
# Start with project structure to understand organization
glob pattern="*/"

# Find main entry points
glob pattern="**/main.{py,js}"
glob pattern="**/index.{js,ts}"
glob pattern="**/app.{py,js,ts}"

# Examine package definitions and dependencies
glob pattern="**/package.json"
glob pattern="**/requirements.txt"
glob pattern="**/pyproject.toml"

# Identify core modules or components
grep pattern="import " include="**/main.py"
grep pattern="import " include="**/index.js"
grep pattern="from " include="**/app.py"

# Find configuration and environment settings
glob pattern="**/{config,conf,settings,env}*.{json,yaml,py,js,env}"

# Look for documentation
glob pattern="**/{README,CONTRIBUTING,ARCHITECTURE}*"
```

Use these techniques to efficiently search through codebases of any size and complexity.
"""

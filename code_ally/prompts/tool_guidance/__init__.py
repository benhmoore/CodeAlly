"""Tool-specific guidance prompts for contextual help.

This package contains detailed guidance for specific tools that can be
injected into the conversation when relevant.
"""

from code_ally.prompts.tool_guidance.git import GIT_GUIDANCE
from code_ally.prompts.tool_guidance.file import FILE_GUIDANCE
from code_ally.prompts.tool_guidance.bash import BASH_GUIDANCE
from code_ally.prompts.tool_guidance.search import SEARCH_GUIDANCE
from code_ally.prompts.tool_guidance.default import DEFAULT_GUIDANCE

# Dictionary mapping tool types to their specific guidance
TOOL_GUIDANCE = {
    "git": GIT_GUIDANCE,
    "file": FILE_GUIDANCE,
    "bash": BASH_GUIDANCE,
    "search": SEARCH_GUIDANCE,
    "default": DEFAULT_GUIDANCE,
}

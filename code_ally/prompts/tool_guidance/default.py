"""Default guidance when no specific tool context applies."""

DEFAULT_GUIDANCE = """
**GENERAL TASK GUIDANCE**

* **Prioritize Action & Verification:** If the request involves creating, running, modifying, finding, or calculating something, use the appropriate tool(s) and verify the result. Direct action is preferred over explanation.
* **Follow Core Workflows:** Adhere strictly to the mandatory workflows outlined in the main system prompt, especially regarding command execution, file operations, path handling, and Git usage.
* **Tool Chaining:** Combine tools logically (e.g., `glob` -> `grep` -> `file_read` -> `file_edit` -> `bash`).
* **Clarity:** Explain *what* you did and *what the result was* based on verified tool output.
* **Completeness:** Ensure all parts of the user's request are addressed.
* **Consult Specific Guidance:** If the task clearly involves Git, file operations, bash, or search, refer to the more detailed guidance for those tools.
* **Pre-Response Check:** Always perform the mental pre-response checklist from the main system prompt before sending your response.
"""

"""Permission management for Code Ally tools."""

import logging
from typing import Any, Dict, Optional

from code_ally.trust import TrustManager, PermissionDeniedError

logger = logging.getLogger(__name__)

class PermissionManager:
    """Manages permission checks for tools."""
    
    def __init__(self, trust_manager: TrustManager):
        """Initialize the permission manager."""
        self.trust_manager = trust_manager
    
    def check_permission(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """Check if a tool has permission to execute."""
        # Get permission path based on the tool and arguments
        permission_path = self._get_permission_path(tool_name, arguments)
        
        # Check if already trusted
        if self.trust_manager.is_trusted(tool_name, permission_path):
            logger.info(f"Tool {tool_name} is already trusted")
            return True
            
        logger.info(f"Requesting permission for {tool_name}")
        
        # Prompt for permission (this may raise PermissionDeniedError)
        return self.trust_manager.prompt_for_permission(tool_name, permission_path)
    
    def _get_permission_path(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Extract the path from tool arguments for permission checking."""
        # Handle bash commands differently
        if tool_name == "bash" and "command" in arguments:
            return arguments
            
        # For other tools, look for path arguments
        for arg_name, arg_value in arguments.items():
            if isinstance(arg_value, str) and arg_name in ("path", "file_path", "directory"):
                return arg_value
                
        return None
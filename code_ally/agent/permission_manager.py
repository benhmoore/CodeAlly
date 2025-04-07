import logging
from typing import Any, Dict, Optional

from code_ally.trust import TrustManager, PermissionDeniedError

logger = logging.getLogger(__name__)


class PermissionManager:
    """Manages permission checks for tools."""
    
    def __init__(self, trust_manager: TrustManager):
        """Initialize the permission manager.
        
        Args:
            trust_manager: The trust manager to use for permission checks
        """
        self.trust_manager = trust_manager
    
    def check_permission(
        self, 
        tool_name: str, 
        arguments: Dict[str, Any], 
        batch_id: Optional[str] = None
    ) -> bool:
        """Check if a tool has permission to execute.
        
        Args:
            tool_name: The name of the tool
            arguments: The arguments for the tool
            batch_id: The batch ID for parallel operations
            
        Returns:
            Whether permission is granted
            
        Raises:
            PermissionDeniedError: If permission is explicitly denied
        """
        # Get permission path based on the tool and arguments
        permission_path = self._get_permission_path(tool_name, arguments)
        
        # Check if already trusted
        if self.trust_manager.is_trusted(tool_name, permission_path, batch_id):
            logger.info(f"Tool {tool_name} is already trusted")
            return True
            
        logger.info(f"Requesting permission for {tool_name}")
        
        # Prompt for permission (this may raise PermissionDeniedError)
        return self.trust_manager.prompt_for_permission(tool_name, permission_path, batch_id)
    
    def _get_permission_path(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Extract the path from tool arguments for permission checking.
        
        Args:
            tool_name: The name of the tool
            arguments: The arguments for the tool
            
        Returns:
            The path to check for permissions, or None
        """
        # Handle bash commands differently
        if tool_name == "bash" and "command" in arguments:
            return arguments
            
        # For other tools, look for path arguments
        for arg_name, arg_value in arguments.items():
            if isinstance(arg_value, str) and arg_name in ("path", "file_path", "directory"):
                return arg_value
                
        return None
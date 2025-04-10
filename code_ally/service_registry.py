"""Service registry for dependency injection and service management."""


class ServiceRegistry:
    """Registry for managing services with a singleton pattern.

    This class provides a central registry for services that can be
    accessed throughout the application. It uses a singleton pattern
    to ensure only one instance exists.
    """

    _instance = None

    @classmethod
    def get_instance(cls):
        """Get the singleton instance of the ServiceRegistry.

        Returns:
            ServiceRegistry: The singleton instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """Initialize an empty service registry."""
        self._services = {}

    def register(self, name, service):
        """Register a service with the given name.

        Args:
            name: The name to register the service under
            service: The service instance to register
        """
        self._services[name] = service

    def get(self, name):
        """Get a service by name.

        Args:
            name: The name of the service to retrieve

        Returns:
            The service instance or None if not found
        """
        return self._services.get(name)

    def has_service(self, name):
        """Check if a service exists in the registry.

        Args:
            name: The name of the service to check

        Returns:
            bool: True if the service exists, False otherwise
        """
        return name in self._services

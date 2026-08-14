from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseAgentRunner(ABC):
    """
    Abstract base class for verification agent runners.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def run_case(self, case_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a benchmark case and return an execution & evidence packet.
        """
        pass

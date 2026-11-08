"""
Domain models reflecting Microsoft Agent Service (Azure AI Agents) concepts:
- Agent: Autonomous agent definition with instructions, model, and tool definitions.
- Thread: Persistent conversation state holding messages.
- Message: Utterance in a thread (User, Assistant, System, Tool).
- ToolDefinition & ToolCall: Function calling schemas and invocation requests.
- Run & RunStatus: Execution lifecycle for agent processing and tool loop.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import time
import uuid


class RunStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    REQUIRES_ACTION = "requires_action"
    COMPLETED = "completed"
    FAILED = "failed"


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Optional[Callable[..., Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolCall:
    id: str
    function_name: str
    arguments: Dict[str, Any]

    @classmethod
    def create(cls, function_name: str, arguments: Dict[str, Any]) -> "ToolCall":
        return cls(
            id=f"call_{uuid.uuid4().hex[:8]}",
            function_name=function_name,
            arguments=arguments,
        )


@dataclass
class ToolOutput:
    tool_call_id: str
    output: str


@dataclass
class Message:
    id: str
    role: MessageRole
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class Run:
    id: str
    thread_id: str
    agent_id: str
    status: RunStatus = RunStatus.QUEUED
    required_tool_calls: List[ToolCall] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


@dataclass
class Thread:
    id: str
    messages: List[Message] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class Agent:
    id: str
    name: str
    instructions: str
    model: str = "gpt-4o"
    tools: List[ToolDefinition] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

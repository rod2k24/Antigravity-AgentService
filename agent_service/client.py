"""
Simulated Microsoft Agent Service Client (Azure AI Agent Service).

Implements the fundamental API contracts and state machine:
- Agent management (create_agent)
- Thread management (create_thread, list_messages, create_message)
- Run lifecycle (create_run, submit_tool_outputs, poll/step)
- Tool execution dispatching

Includes didactic logging callbacks for console visualization.
"""

from typing import Any, Callable, Dict, List, Optional
import time
import uuid

from .models import (
    Agent,
    Message,
    MessageRole,
    Run,
    RunStatus,
    Thread,
    ToolCall,
    ToolDefinition,
    ToolOutput,
)
from .simulator import AgentExecutionSimulator


class AgentServiceClient:
    """
    Didactic implementation of the Microsoft Azure AI Agent Service Client.
    """

    def __init__(self, logger: Optional[Callable[[str, str], None]] = None):
        self.agents: Dict[str, Agent] = {}
        self.threads: Dict[str, Thread] = {}
        self.runs: Dict[str, Run] = {}
        self.tool_registry: Dict[str, ToolDefinition] = {}
        self.logger = logger or (lambda tag, msg: None)

    # -------------------------------------------------------------
    # Agent Operations
    # -------------------------------------------------------------
    def create_agent(
        self,
        name: str,
        instructions: str,
        model: str = "gpt-4o",
        tools: Optional[List[ToolDefinition]] = None,
        agent_id: Optional[str] = None
    ) -> Agent:
        """Creates and registers a new autonomous agent."""
        agent_id = agent_id or f"agent_{uuid.uuid4().hex[:8]}"
        tools = tools or []
        agent = Agent(
            id=agent_id,
            name=name,
            instructions=instructions,
            model=model,
            tools=tools
        )
        self.agents[agent_id] = agent
        for t in tools:
            self.tool_registry[t.name] = t

        self.logger("SERVICE", f"Registered Agent: [{agent.name}] (ID: {agent.id}, Model: {agent.model}, Tools: {len(tools)})")
        return agent

    # -------------------------------------------------------------
    # Thread Operations
    # -------------------------------------------------------------
    def create_thread(self, metadata: Optional[Dict[str, Any]] = None) -> Thread:
        """Creates a new stateful conversation thread."""
        thread_id = f"thread_{uuid.uuid4().hex[:8]}"
        thread = Thread(id=thread_id, metadata=metadata or {})
        self.threads[thread_id] = thread
        self.logger("THREAD", f"Initialized Thread '{thread_id}'")
        return thread

    def create_message(
        self,
        thread_id: str,
        role: MessageRole,
        content: str,
        tool_call_id: Optional[str] = None
    ) -> Message:
        """Appends a message to a thread."""
        thread = self.threads.get(thread_id)
        if not thread:
            raise ValueError(f"Thread '{thread_id}' not found.")
        
        msg = Message(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            role=role,
            content=content,
            tool_call_id=tool_call_id
        )
        thread.messages.append(msg)
        return msg

    def list_messages(self, thread_id: str) -> List[Message]:
        """Retrieves all messages in chronological order."""
        thread = self.threads.get(thread_id)
        if not thread:
            raise ValueError(f"Thread '{thread_id}' not found.")
        return thread.messages

    # -------------------------------------------------------------
    # Run Lifecycle Operations
    # -------------------------------------------------------------
    def create_run(self, thread_id: str, agent_id: str) -> Run:
        """Initiates an agent run against a thread."""
        if thread_id not in self.threads:
            raise ValueError(f"Thread '{thread_id}' not found.")
        if agent_id not in self.agents:
            raise ValueError(f"Agent '{agent_id}' not found.")

        run_id = f"run_{uuid.uuid4().hex[:8]}"
        run = Run(
            id=run_id,
            thread_id=thread_id,
            agent_id=agent_id,
            status=RunStatus.QUEUED
        )
        self.runs[run_id] = run
        self.logger("RUN", f"Run '{run_id}' created for Agent '{self.agents[agent_id].name}' on Thread '{thread_id}' (Status: QUEUED)")
        return run

    def step_run(self, run_id: str, tool_outputs_submitted: bool = False) -> Run:
        """
        Advances the execution state machine of the Run.
        Transitions:
        QUEUED -> IN_PROGRESS -> REQUIRES_ACTION (Tool calls requested)
                              -> COMPLETED (Final assistant response added to thread)
        """
        run = self.runs.get(run_id)
        if not run:
            raise ValueError(f"Run '{run_id}' not found.")
        
        thread = self.threads[run.thread_id]
        agent = self.agents[run.agent_id]

        if run.status in (RunStatus.QUEUED, RunStatus.IN_PROGRESS):
            run.status = RunStatus.IN_PROGRESS
            self.logger("RUN", f"Run '{run_id}' transitioned to IN_PROGRESS. Agent '{agent.name}' is reasoning...")

            # Evaluate next step using the execution simulator
            tool_calls, response_text = AgentExecutionSimulator.evaluate_step(
                agent=agent,
                messages=thread.messages,
                tool_outputs_recently_added=tool_outputs_submitted
            )

            if tool_calls:
                run.status = RunStatus.REQUIRES_ACTION
                run.required_tool_calls = tool_calls
                call_names = ", ".join(f"{c.function_name}({c.arguments})" for c in tool_calls)
                self.logger("TOOL_CALL", f"Agent '{agent.name}' requests tool execution: [{call_names}]")
            elif response_text is not None:
                # Add assistant message to thread
                self.create_message(run.thread_id, MessageRole.ASSISTANT, response_text)
                run.status = RunStatus.COMPLETED
                self.logger("RUN", f"Run '{run_id}' transitioned to COMPLETED. Response added to thread.")
        
        return run

    def submit_tool_outputs(self, thread_id: str, run_id: str, tool_outputs: List[ToolOutput]) -> Run:
        """
        Submits the outputs of executed tool calls back into the thread,
        allowing the agent to consume the results and continue execution.
        """
        run = self.runs.get(run_id)
        if not run or run.status != RunStatus.REQUIRES_ACTION:
            raise ValueError(f"Run '{run_id}' is not awaiting tool action.")

        for out in tool_outputs:
            self.create_message(
                thread_id=thread_id,
                role=MessageRole.TOOL,
                content=out.output,
                tool_call_id=out.tool_call_id
            )
            self.logger("TOOL_OUTPUT", f"Submitted output for [{out.tool_call_id}]: {out.output}")

        run.required_tool_calls = []
        run.status = RunStatus.IN_PROGRESS
        # Step the run with the newly added tool outputs
        return self.step_run(run_id, tool_outputs_submitted=True)

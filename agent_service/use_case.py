"""
Didactic Multi-Agent System Setup for Microsoft Agent Service:
- Orchestrator Agent: CloudStore 360 Concierge
- Specialized Agent 1: Billing & Accounts Specialist
- Specialized Agent 2: Technical Diagnostics Specialist

Demonstrates the Supervisor/Delegation pattern where the Orchestrator
delegates sub-tasks to specialized agents and synthesizes the final response.
"""

import json
from typing import Callable, Optional
from .client import AgentServiceClient
from .models import Agent, MessageRole, RunStatus, ToolDefinition, ToolOutput
from .tools import (
    TOOL_LOOKUP_INVOICE,
    TOOL_PROCESS_REFUND,
    TOOL_CHECK_SERVICE_HEALTH,
    TOOL_RESTART_SERVICE,
)


class MultiAgentSystem:
    """
    Encapsulates the complete multi-agent topology:
    - 1 Orchestrator Agent
    - 2 Specialized Agents with domain tools
    """

    def __init__(self, client: AgentServiceClient):
        self.client = client
        self.billing_agent: Optional[Agent] = None
        self.tech_agent: Optional[Agent] = None
        self.orchestrator_agent: Optional[Agent] = None
        self._setup_agents()

    def _setup_agents(self):
        # 1. Specialized Agent: Billing Specialist
        self.billing_agent = self.client.create_agent(
            agent_id="agent_billing_specialist",
            name="BillingSpecialistAgent",
            instructions=(
                "You are an expert Billing Specialist. You inspect customer invoices, "
                "verify discrepancies, and issue refunds or credits using provided billing tools."
            ),
            model="gpt-4o",
            tools=[TOOL_LOOKUP_INVOICE, TOOL_PROCESS_REFUND],
        )

        # 2. Specialized Agent: Technical Diagnostics Specialist
        self.tech_agent = self.client.create_agent(
            agent_id="agent_tech_specialist",
            name="TechnicalDiagnosticsAgent",
            instructions=(
                "You are a Site Reliability and Technical Support Specialist. You inspect "
                "microservice telemetry, detect degradation, and perform rolling container restarts."
            ),
            model="gpt-4o",
            tools=[TOOL_CHECK_SERVICE_HEALTH, TOOL_RESTART_SERVICE],
        )

        # 3. Delegation Handlers for the Orchestrator
        def handle_delegate_to_billing(sub_query: str, invoice_id: str = "") -> str:
            self.client.logger("DELEGATION", f"➡️ Orchestrator delegating to BillingSpecialistAgent: '{sub_query}'")
            return self._execute_specialist(self.billing_agent, sub_query)

        def handle_delegate_to_tech(sub_query: str, target_service: str = "") -> str:
            self.client.logger("DELEGATION", f"➡️ Orchestrator delegating to TechnicalDiagnosticsAgent: '{sub_query}'")
            return self._execute_specialist(self.tech_agent, sub_query)

        # Tool definitions exposed to the Orchestrator
        tool_delegate_billing = ToolDefinition(
            name="delegate_to_billing_agent",
            description="Delegate billing, payment, invoice, and refund requests to the Billing Specialist Agent.",
            parameters={
                "type": "object",
                "properties": {
                    "sub_query": {"type": "string", "description": "The specific billing query or request."},
                    "invoice_id": {"type": "string", "description": "The invoice ID if mentioned."}
                },
                "required": ["sub_query"]
            },
            handler=handle_delegate_to_billing
        )

        tool_delegate_tech = ToolDefinition(
            name="delegate_to_tech_agent",
            description="Delegate technical incidents, service degradation, and restart requests to the Tech Agent.",
            parameters={
                "type": "object",
                "properties": {
                    "sub_query": {"type": "string", "description": "The technical issue description."},
                    "target_service": {"type": "string", "description": "The target microservice name."}
                },
                "required": ["sub_query"]
            },
            handler=handle_delegate_to_tech
        )

        # 4. Orchestrator Agent
        self.orchestrator_agent = self.client.create_agent(
            agent_id="agent_orchestrator",
            name="ConciergeOrchestrator",
            instructions=(
                "You are the CloudStore 360 Enterprise Concierge. You triage customer inquiries, "
                "delegate sub-tasks to specialized agents (Billing and Tech), and produce a cohesive "
                "executive summary for the customer."
            ),
            model="gpt-4o",
            tools=[tool_delegate_billing, tool_delegate_tech],
        )

    def _execute_specialist(self, specialist_agent: Agent, query: str) -> str:
        """
        Runs a specialized agent in an isolated thread to resolve a sub-task.
        Executes the agent's internal tool loop until completion.
        """
        # Create a dedicated thread for the specialist sub-task
        specialist_thread = self.client.create_thread(metadata={"parent": "orchestrator", "specialist": specialist_agent.name})
        self.client.create_message(specialist_thread.id, MessageRole.USER, query)

        # Run the specialist
        run = self.client.create_run(specialist_thread.id, specialist_agent.id)
        run = self.client.step_run(run.id)

        # Execute the specialist's tool loop
        while run.status == RunStatus.REQUIRES_ACTION:
            tool_outputs = []
            for call in run.required_tool_calls:
                tool_def = self.client.tool_registry.get(call.function_name)
                if tool_def and tool_def.handler:
                    self.client.logger("TOOL_EXEC", f"[{specialist_agent.name}] Executing local tool '{call.function_name}' with args {call.arguments}")
                    result_str = tool_def.handler(**call.arguments)
                else:
                    result_str = json.dumps({"error": f"Tool '{call.function_name}' not implemented."})
                
                tool_outputs.append(ToolOutput(tool_call_id=call.id, output=result_str))

            run = self.client.submit_tool_outputs(specialist_thread.id, run.id, tool_outputs)

        # Retrieve the specialist's final assistant message
        messages = self.client.list_messages(specialist_thread.id)
        assistant_msgs = [m for m in messages if m.role == MessageRole.ASSISTANT]
        result = assistant_msgs[-1].content if assistant_msgs else "No response generated by specialist."
        return json.dumps({"specialist": specialist_agent.name, "result": result})

    def process_customer_query(self, user_query: str, thread_id: Optional[str] = None) -> str:
        """
        Processes an incoming query through the Orchestrator and returns the final synthesized response.
        """
        # 1. Ensure a customer conversation thread exists
        if not thread_id:
            thread = self.client.create_thread(metadata={"channel": "console_concierge"})
            thread_id = thread.id

        # 2. Add customer message
        self.client.create_message(thread_id, MessageRole.USER, user_query)

        # 3. Create run for Orchestrator
        run = self.client.create_run(thread_id, self.orchestrator_agent.id)
        run = self.client.step_run(run.id)

        # 4. Handle Orchestrator tool calls (e.g. delegations)
        while run.status == RunStatus.REQUIRES_ACTION:
            tool_outputs = []
            for call in run.required_tool_calls:
                tool_def = self.client.tool_registry.get(call.function_name)
                if tool_def and tool_def.handler:
                    self.client.logger("TOOL_EXEC", f"[ConciergeOrchestrator] Executing '{call.function_name}' with {call.arguments}")
                    result_str = tool_def.handler(**call.arguments)
                else:
                    result_str = json.dumps({"error": f"Tool '{call.function_name}' handler not found."})
                
                tool_outputs.append(ToolOutput(tool_call_id=call.id, output=result_str))

            run = self.client.submit_tool_outputs(thread_id, run.id, tool_outputs)

        # 5. Extract final response
        messages = self.client.list_messages(thread_id)
        final_msgs = [m for m in messages if m.role == MessageRole.ASSISTANT]
        return final_msgs[-1].content if final_msgs else "No response."

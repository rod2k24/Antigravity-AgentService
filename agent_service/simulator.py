"""
Didactic Execution and Simulation Engine.
Simulates LLM function calling and reasoning for:
1. Orchestrator Agent (Triage, routing to specialized agents)
2. Billing Specialist Agent (Calls billing tools, handles refunds)
3. Technical Support Specialist Agent (Calls diagnostics & restart tools)

This allows the console application to run completely standalone without requiring
external OpenAI or Azure API keys, while strictly obeying the Microsoft Agent Service lifecycle.
"""

import json
import re
from typing import List, Optional, Tuple
from .models import Agent, Message, Run, RunStatus, ToolCall, ToolOutput


def extract_invoice_id(text: str) -> Optional[str]:
    """Helper to extract invoice numbers or identifiers from natural language queries."""
    match = re.search(r"(?:invoice|inv|bill)\s*(?:number|no\.?|#)?\s*([a-zA-Z0-9\-]+)", text, re.IGNORECASE)
    if match:
        val = match.group(1).strip()
        if val.lower() not in ("details", "please", "the", "my", "a", "an", "is", "for"):
            return val.upper()
    direct_match = re.search(r"\b(inv-[a-zA-Z0-9]+|[0-9]{3,}[a-zA-Z0-9]*)\b", text, re.IGNORECASE)
    if direct_match:
        return direct_match.group(1).upper()
    return None


class AgentExecutionSimulator:
    """Simulates agent decision making (LLM prompt-to-tool-calling cycle)."""

    @staticmethod
    def evaluate_step(
        agent: Agent,
        messages: List[Message],
        tool_outputs_recently_added: bool = False
    ) -> Tuple[Optional[List[ToolCall]], Optional[str]]:
        """
        Determines the next action for an agent given the message history:
        Returns: (tool_calls, final_assistant_message)
        - If tool_calls is not None, the run transitions to 'requires_action'.
        - If final_assistant_message is not None, the run transitions to 'completed'.
        """
        # Collect conversation text
        user_queries = [m.content for m in messages if m.role == "user"]
        latest_user_query = user_queries[-1] if user_queries else ""

        # Check existing tool messages in this thread
        tool_messages = [m for m in messages if m.role == "tool"]

        # ==========================================================
        # 1. ORCHESTRATOR AGENT BEHAVIOR
        # ==========================================================
        if agent.id == "agent_orchestrator":
            # If we just received tool outputs from delegated sub-agents:
            if tool_outputs_recently_added or tool_messages:
                # Check if we still have remaining delegations or if we are done
                # Synthesize final response from delegated agents
                delegation_reports = [m.content for m in tool_messages]
                synthesis = (
                    "Thank you for contacting CloudStore 360 Enterprise Support. "
                    "I have coordinated with our specialized departments to address your request:\n\n"
                )
                for i, report in enumerate(delegation_reports, 1):
                    try:
                        data = json.loads(report)
                        result = data.get("result", report)
                    except Exception:
                        result = report
                    synthesis += f"• **Specialist Update #{i}**: {result}\n\n"
                synthesis += "All requested actions have been concluded. Please let me know if you need anything else!"
                return None, synthesis

            # Initial triage: inspect user query and decide delegation
            query_lower = latest_user_query.lower()
            delegations = []

            needs_billing = any(w in query_lower for w in ["invoice", "refund", "charge", "bill", "payment", "inv-", "dollar", "$"])
            needs_tech = any(w in query_lower for w in ["down", "service", "gateway", "auth", "health", "restart", "500", "error", "latency", "pod", "cluster"])

            if needs_billing:
                # Extract customer or invoice hint
                inv_id = extract_invoice_id(latest_user_query) or "INV-8821"
                delegations.append(
                    ToolCall.create(
                        "delegate_to_billing_agent",
                        {
                            "sub_query": latest_user_query,
                            "invoice_id": inv_id
                        }
                    )
                )

            if needs_tech:
                # Extract service hint
                svc_name = "payment-gateway"
                if "auth" in query_lower:
                    svc_name = "auth-service"
                elif "inventory" in query_lower:
                    svc_name = "inventory-api"
                delegations.append(
                    ToolCall.create(
                        "delegate_to_tech_agent",
                        {
                            "sub_query": latest_user_query,
                            "target_service": svc_name
                        }
                    )
                )

            # Fallback if no specific keyword matched
            if not delegations:
                return None, (
                    "Welcome to CloudStore Concierge! I can assist you with Billing "
                    "(invoices, refunds) or Technical Support (service health, restarts). "
                    "How can I help you today?"
                )

            return delegations, None

        # ==========================================================
        # 2. BILLING SPECIALIST AGENT BEHAVIOR
        # ==========================================================
        elif agent.id == "agent_billing_specialist":
            query_lower = latest_user_query.lower()
            invoice_id = extract_invoice_id(latest_user_query) or "INV-8821"

            # Check if lookup_invoice was already executed
            lookup_output = None
            lookup_error = None
            refund_output = None
            for tm in tool_messages:
                try:
                    data = json.loads(tm.content)
                    if data.get("success") is False:
                        lookup_error = data.get("error", "Invoice lookup failed.")
                    elif "invoice" in data:
                        lookup_output = data["invoice"]
                    if "transaction_id" in data:
                        refund_output = data
                except Exception:
                    pass

            # Handle case where lookup returned an error
            if lookup_error:
                return None, f"Invoice lookup for '{invoice_id}': {lookup_error}"

            # Step A: If lookup hasn't happened yet, request lookup_invoice
            if not lookup_output:
                return [
                    ToolCall.create("lookup_invoice", {"invoice_id": invoice_id})
                ], None

            # Step B: Lookup was done. Check if refund was requested and not yet processed
            wants_refund = any(w in query_lower for w in ["refund", "duplicate", "credit", "return"])
            if wants_refund and not refund_output:
                amount = lookup_output.get("amount", 120.00)
                reason = "Duplicate charge customer dispute resolved via Agent Service"
                return [
                    ToolCall.create(
                        "process_refund",
                        {
                            "invoice_id": invoice_id,
                            "amount": amount,
                            "reason": reason
                        }
                    )
                ], None

            # Step C: All tools done, finalize response
            if refund_output:
                reply = (
                    f"Invoice {invoice_id} ({lookup_output.get('customer')}) was inspected. "
                    f"A duplicate charge of ${lookup_output.get('amount'):.2f} was confirmed. "
                    f"Refund successfully issued under confirmation ID {refund_output.get('transaction_id')}. "
                    f"Current status: {refund_output.get('updated_status')}."
                )
            else:
                reply = (
                    f"Invoice {invoice_id} details retrieved: Customer '{lookup_output.get('customer')}', "
                    f"Total: ${lookup_output.get('amount'):.2f} {lookup_output.get('currency')}, "
                    f"Status: {lookup_output.get('status')}, Items: {', '.join(lookup_output.get('items', []))}."
                )
            return None, reply

        # ==========================================================
        # 3. TECHNICAL SUPPORT AGENT BEHAVIOR
        # ==========================================================
        elif agent.id == "agent_tech_specialist":
            query_lower = latest_user_query.lower()
            target_svc = "payment-gateway"
            if "auth" in query_lower:
                target_svc = "auth-service"
            elif "inventory" in query_lower:
                target_svc = "inventory-api"

            health_output = None
            restart_output = None
            for tm in tool_messages:
                try:
                    data = json.loads(tm.content)
                    if "health" in data:
                        health_output = data["health"]
                    if "action" in data:
                        restart_output = data
                except Exception:
                    pass

            # Step A: Check health first if not checked
            if not health_output:
                return [
                    ToolCall.create("check_service_health", {"service_name": target_svc})
                ], None

            # Step B: If degraded or user explicitly asked for restart, and restart not yet done
            is_degraded = health_output.get("status") == "DEGRADED"
            wants_restart = any(w in query_lower for w in ["restart", "fix", "recover", "reboot"])
            if (is_degraded or wants_restart) and not restart_output:
                return [
                    ToolCall.create("restart_service", {"service_name": target_svc, "region": health_output.get("cluster", "prod-us-east-1")})
                ], None

            # Step C: Summarize
            if restart_output:
                reply = (
                    f"Service '{target_svc}' diagnostic found status '{health_output.get('status')}' "
                    f"with {health_output.get('http_500_rate')} error rate in cluster {health_output.get('cluster')}. "
                    f"Executed rolling container restart. New status: '{restart_output.get('new_status')}' "
                    f"with latency normal at 38ms."
                )
            else:
                reply = (
                    f"Service '{target_svc}' is currently {health_output.get('status')} in cluster "
                    f"{health_output.get('cluster')}. Latency: {health_output.get('latency_ms')}ms, "
                    f"500 Error rate: {health_output.get('http_500_rate')}."
                )
            return None, reply

        # Default fallback
        return None, "Request processed."

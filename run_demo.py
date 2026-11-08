#!/usr/bin/env python3
"""
Microsoft Agent Service - Didactic Console Application.

Demonstrates:
- Azure AI Agent Service architecture (Agent, Thread, Run, Tool Call loop)
- 1 Orchestrator Agent (Concierge)
- 2 Specialized Agents:
  - BillingSpecialistAgent (Tools: lookup_invoice, process_refund)
  - TechnicalDiagnosticsAgent (Tools: check_service_health, restart_service)
- Simulated Tool Calling and Multi-Agent Delegation without external dependencies.
"""

import sys
import time
from typing import Optional

from agent_service.client import AgentServiceClient
from agent_service.use_case import MultiAgentSystem
from agent_service.tools import INVOICES_DB, SERVICES_DB

# ANSI Colors for clean didactic console presentation
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
RED = "\033[31m"
BG_BLUE = "\033[44m\033[37m"


def console_logger(category: str, message: str) -> None:
    """Format and display real-time service events."""
    timestamp = time.strftime("%H:%M:%S")
    prefix = f"{DIM}[{timestamp}]{RESET}"

    if category == "SERVICE":
        print(f"{prefix} {CYAN}⚙️  [SERVICE]      {message}{RESET}")
    elif category == "THREAD":
        print(f"{prefix} {BLUE}🧵 [THREAD]       {message}{RESET}")
    elif category == "RUN":
        print(f"{prefix} {MAGENTA}⚡ [RUN]          {message}{RESET}")
    elif category == "DELEGATION":
        print(f"{prefix} {BOLD}{YELLOW}🔀 [DELEGATE]     {message}{RESET}")
    elif category == "TOOL_CALL":
        print(f"{prefix} {YELLOW}🛠️  [TOOL_CALL]    {message}{RESET}")
    elif category == "TOOL_EXEC":
        print(f"{prefix} {GREEN}🔧 [TOOL_EXEC]    {message}{RESET}")
    elif category == "TOOL_OUTPUT":
        print(f"{prefix} {DIM}📥 [TOOL_OUTPUT]  {message}{RESET}")
    else:
        print(f"{prefix} [{category}] {message}")


def print_banner():
    print(f"\n{BOLD}{CYAN}========================================================================={RESET}")
    print(f"{BOLD}{CYAN}      MICROSOFT AGENT SERVICE (AZURE AI AGENTS) - DIDACTIC CONSOLE       {RESET}")
    print(f"{BOLD}{CYAN}========================================================================={RESET}")
    print(f"{DIM}Learn how Microsoft Agent Service orchestrates specialized agents and tools.{RESET}")
    print(f"Architecture:")
    print(f"  • {BOLD}ConciergeOrchestrator{RESET}  -> Triage, Intent Detection, Sub-agent Delegation")
    print(f"  • {BOLD}BillingSpecialistAgent{RESET} -> Invoices & Refunds (Tools: lookup_invoice, process_refund)")
    print(f"  • {BOLD}TechnicalDiagnosticsAgent{RESET} -> SRE & Infra (Tools: check_service_health, restart_service)\n")


def print_database_snapshot():
    print(f"\n{BOLD}📊 Initial Mock Environment Snapshot:{RESET}")
    print(f"{DIM}Invoices DB:{RESET}")
    for k, v in INVOICES_DB.items():
        print(f"  • [{k}] {v['customer']} - ${v['amount']:.2f} ({v['status']})")
    print(f"{DIM}Microservices DB:{RESET}")
    for k, v in SERVICES_DB.items():
        status_color = GREEN if "HEALTHY" in v['status'] else RED
        print(f"  • [{k}] Region: {v['cluster']} | Status: {status_color}{v['status']}{RESET} | 500 Rate: {v['http_500_rate']}")
    print()


def run_scenario(system: MultiAgentSystem, title: str, user_query: str):
    print(f"\n{BOLD}{BG_BLUE} 🎯 SCENARIO: {title} {RESET}")
    print(f"{BOLD}Customer User Prompt:{RESET} \"{user_query}\"\n")
    print(f"{DIM}--- Execution Trace Starting (Watch Thread, Run, and Tool events) ---{RESET}")

    start_time = time.time()
    response = system.process_customer_query(user_query)
    elapsed = time.time() - start_time

    print(f"{DIM}--- Execution Trace Completed in {elapsed:.2f}s ---{RESET}\n")
    print(f"{BOLD}{GREEN}🤖 Final Response to Customer:{RESET}")
    print(f"{response}\n")
    print(f"{CYAN}{'-'*73}{RESET}")


def main():
    print_banner()

    # Initialize the client with real-time console tracing
    client = AgentServiceClient(logger=console_logger)
    system = MultiAgentSystem(client)

    scenarios = [
        (
            "1. Billing & Refund Request",
            "Billing Dispute",
            "Hello, my invoice INV-8821 was charged twice ($120.00) due to a glitch. Can you inspect it and process a refund?"
        ),
        (
            "2. Technical Incident & Container Restart",
            "Site Reliability Incident",
            "Alert: Our payment-gateway service in prod-us-east-1 is throwing 500 errors and degraded! Please check its health and restart it."
        ),
        (
            "3. Combined Multi-Domain Inquiry",
            "Multi-Agent Coordination",
            "Can you check if our auth-service is healthy, and also verify if invoice INV-4010 has been paid?"
        )
    ]

    if "--all" in sys.argv:
        print_database_snapshot()
        for _, name, query in scenarios:
            run_scenario(system, name, query)
        print(f"\n{BOLD}{GREEN}✅ All didactic walkthrough scenarios completed successfully!{RESET}\n")
        return

    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        arg = sys.argv[1].strip()
        if arg in ("1", "2", "3"):
            idx = int(arg) - 1
            _, name, query = scenarios[idx]
            print_database_snapshot()
            run_scenario(system, name, query)
            return
        else:
            # Custom prompt passed via CLI
            query = " ".join(sys.argv[1:])
            print_database_snapshot()
            run_scenario(system, "Custom CLI Request", query)
            return

    while True:
        print_database_snapshot()
        print(f"{BOLD}Choose a didactic scenario to explore:{RESET}")
        for i, (label, _, _) in enumerate(scenarios, 1):
            print(f"  [{i}] {label}")
        print(f"  [4] Interactive Mode (Type your own custom prompt)")
        print(f"  [5] Run All Scenarios Sequentially")
        print(f"  [q] Quit")

        try:
            choice = input(f"\n{BOLD}Select an option [1-5, q]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n\nExiting console application. Goodbye!\n")
            break

        if choice.lower() in ("q", "quit", "exit"):
            print(f"\nGoodbye!\n")
            break
        elif choice in ("1", "2", "3"):
            idx = int(choice) - 1
            _, name, query = scenarios[idx]
            run_scenario(system, name, query)
        elif choice == "4":
            print(f"\n{BOLD}--- Interactive Console ---{RESET}")
            print(f"{DIM}Type your query (or 'back' to return to menu). You can ask about invoices (INV-8821, INV-4010, INV-1002) or services (payment-gateway, auth-service, inventory-api):{RESET}\n")
            while True:
                try:
                    prompt = input(f"{BOLD}Customer > {RESET}").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not prompt or prompt.lower() in ("back", "exit"):
                    break
                run_scenario(system, "Interactive Custom Request", prompt)
        elif choice == "5":
            for _, name, query in scenarios:
                run_scenario(system, name, query)
        else:
            print(f"{RED}Invalid selection. Please choose 1-5 or q.{RESET}")


if __name__ == "__main__":
    main()

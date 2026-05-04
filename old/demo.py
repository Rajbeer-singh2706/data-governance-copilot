"""
Data Governance Copilot — Quick Start Demo
==========================================
Run this script to see the full multi-agent system in action.

Usage:
    python demo.py

No credentials required — runs fully in mock mode.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from datetime import datetime

# Force mock mode for demo
os.environ["ENABLE_MOCK"] = "true"

from config.settings import config
from agents.supervisor_agent import SupervisorAgent

# ── ANSI colours ──────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
DIM    = "\033[2m"
BLUE   = "\033[94m"


def divider(char="─", width=72, color=DIM):
    print(f"{color}{char * width}{RESET}")


def section(title: str):
    print(f"\n{BOLD}{CYAN}{'━' * 72}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'━' * 72}{RESET}\n")


def print_response(resp, query_num: int):
    """Pretty-print a SupervisorResponse to the terminal."""
    section(f"Query {query_num}: {resp.query[:70]}")

    # Intent + timing
    print(f"  {BOLD}Intent    :{RESET} {YELLOW}{resp.intent}{RESET}")
    print(f"  {BOLD}Products  :{RESET} {', '.join(resp.data_products_referenced)}")
    print(f"  {BOLD}Confidence:{RESET} {GREEN}{resp.overall_confidence:.0%}{RESET}")
    print(f"  {BOLD}Time      :{RESET} {resp.execution_time_ms:.0f}ms\n")

    # Agent breakdown
    divider()
    print(f"  {BOLD}{BLUE}AGENT RESULTS{RESET}")
    divider()
    for ar in resp.agent_results:
        icon = f"{GREEN}✓{RESET}" if ar["success"] else f"{RED}✗{RESET}"
        ms   = ar.get("execution_time_ms", 0)
        conf = ar.get("confidence", 0)
        print(f"\n  {icon} {BOLD}{ar['agent']}{RESET}  {DIM}({ms:.0f}ms | conf {conf:.0%}){RESET}")
        # Print first 280 chars of summary
        summary_preview = ar.get("summary", "")[:280].replace("\n", "\n      ")
        print(f"      {summary_preview}")
        if ar.get("error"):
            print(f"      {RED}Error: {ar['error']}{RESET}")

    # Final LLM synthesis
    divider()
    print(f"\n  {BOLD}{GREEN}COPILOT FINAL SUMMARY{RESET}")
    divider()
    print()
    for line in resp.final_summary.split("\n"):
        print(f"  {line}")

    # Actions
    if resp.recommended_actions:
        print(f"\n  {BOLD}{YELLOW}RECOMMENDED ACTIONS{RESET}")
        for action in resp.recommended_actions:
            print(f"  → {action}")

    # Auto-tickets
    if resp.auto_created_tickets:
        print(f"\n  {BOLD}{GREEN}AUTO-CREATED JIRA TICKETS{RESET}")
        for t in resp.auto_created_tickets:
            print(f"  🎫 {t}")

    print()


# ── Demo queries ──────────────────────────────────────────────────────────────

DEMO_QUERIES = [
    {
        "query": "Why did retention drop last month?",
        "time_range": "last_month",
        "products": None,
        "description": "Full diagnostic — triggers all 4 read agents",
    },
    {
        "query": "What is the data quality score for CAC?",
        "time_range": None,
        "products": ["cac"],
        "description": "DQ focus — metadata + information agents",
    },
    {
        "query": "Who owns the bookings dataset and what are its data sources?",
        "time_range": None,
        "products": ["bookings"],
        "description": "Governance query — metadata + knowledge agents",
    },
    {
        "query": "Show me open Jira bugs and incidents for retention",
        "time_range": None,
        "products": ["retention"],
        "description": "Operations query — capacity agent only",
    },
    {
        "query": "Create a data quality rule for retention completeness",
        "time_range": None,
        "products": ["retention"],
        "description": "WRITE — rule creation via rule agent",
    },
    {
        "query": "Create a bug ticket for the EU region missing data issue",
        "time_range": None,
        "products": ["retention"],
        "description": "WRITE — Jira ticket creation via capacity agent",
    },
    {
        "query": "What is LTV and how is the LTV/CAC ratio calculated?",
        "time_range": None,
        "products": ["ltv", "cac"],
        "description": "Knowledge lookup — RAG over business documentation",
    },
]


def main():
    print(f"\n{BOLD}{CYAN}")
    print("  ╔══════════════════════════════════════════════════════════════════╗")
    print("  ║         🏛️  DATA GOVERNANCE COPILOT  —  DEMO RUN               ║")
    print("  ║              Multi-Agent AI System  |  Mock Mode ON             ║")
    print("  ╚══════════════════════════════════════════════════════════════════╝")
    print(RESET)
    print(f"  {DIM}Timestamp: {datetime.utcnow().isoformat()}Z{RESET}")
    print(f"  {DIM}Running {len(DEMO_QUERIES)} demo queries across 5 specialized agents{RESET}\n")

    # Initialise supervisor
    print(f"  {YELLOW}▶ Initializing SupervisorAgent ...{RESET}")
    supervisor = SupervisorAgent(config=config, enable_mock=True)
    health = supervisor.health_check()
    print(f"  {GREEN}✓ All agents healthy: {list(health['agents'].keys())}{RESET}\n")

    # Run demo queries
    for i, demo in enumerate(DEMO_QUERIES, 1):
        print(f"\n  {DIM}[{i}/{len(DEMO_QUERIES)}] {demo['description']}{RESET}")
        response = supervisor.run(
            query=demo["query"],
            time_range=demo.get("time_range"),
            data_products=demo.get("products"),
        )
        print_response(response, i)

        if i < len(DEMO_QUERIES):
            input(f"  {DIM}Press ENTER for next query ...{RESET}")

    # Final summary
    print(f"\n{BOLD}{GREEN}")
    print("  ╔══════════════════════════════════════════════════════════════════╗")
    print("  ║  ✅  DEMO COMPLETE — All agents executed successfully            ║")
    print("  ╚══════════════════════════════════════════════════════════════════╝")
    print(RESET)
    print(f"  {DIM}To launch the web UI:   streamlit run ui/app.py{RESET}")
    print(f"  {DIM}To start the REST API:  python ui/api.py{RESET}")
    print(f"  {DIM}To run tests:           pytest tests/ -v{RESET}\n")


if __name__ == "__main__":
    main()

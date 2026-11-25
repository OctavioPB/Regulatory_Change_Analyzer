"""Agentic features built on Claude tool use.

- ``loop``            generic tool-use loop (streams text, runs tools, enforces limits)
- ``tools``           read-only database tools shared by every agent
- ``research_agent``  chat agent that decides what to look up (multi-step Q&A)
- ``addendum_team``   orchestrator → one drafting subagent per contract → reviewer agent
"""

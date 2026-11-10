---
name: grilling
description: Stress-test a plan, decision, or idea one question at a time when the user asks to be grilled or challenges an approach. Use grill-with-docs when decisions must persist in local planning documents.
---

# Grilling

Read [the shared interview rules](../_shared/interview.md) and follow conversational mode. Research discoverable facts, challenge assumptions, and ask one consequential question with a recommendation. Wait for the answer before advancing.

This skill does not create or update exploration, specifications, glossary entries, or ADRs. If the user requests durable decisions or domain-document updates, use `grill-with-docs` by reading its `SKILL.md` through the host's supported skill mechanism or file reader. Do not assume a tool named `Skill` exists.

Finish when the decision tree has no unresolved consequential branch and the user confirms shared understanding. Planning agreement does not authorize implementation or Git actions.

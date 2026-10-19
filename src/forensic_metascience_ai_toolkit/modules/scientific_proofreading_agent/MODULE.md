---
name: scientific_proofreading_agent
kind: agent
producer: science_error        # STORED value, hashed into finding_id -- never rename
label: science_agent
order: 20
backend_configurable: true
display: Scientific proofreading agent
prompt: prompt.md
---
# Scientific proofreading agent

The methodology and internal-consistency analyst (formerly the "science-error
analyst"). It covers contradictions, CONSORT flow and implausible claims. Web
search is on, and it can run sandboxed Python (`run_python_script`).

- **Output:** findings-v2 rows with producer `science_error`. A number it
  computed in a script is `agent_code`, capped at provisional 4.

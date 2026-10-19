---
name: adjudicator
kind: finalizer
producer: null
label: adjudicator
order: 90
backend_configurable: true
display: Adjudicator
prompt: prompt.md
---
# Adjudicator

The finaliser. It reads the docket of every producer's rows and assigns each
one its final 1-9 severity, under code-enforced clamps (`adjudicate.apply`).

Without this module, the core finalises through `adjudicate.apply_skip`: the
severities stay provisional, and the reason recorded is "not configured".

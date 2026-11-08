---
version: v1
title: Zero-shot baseline
structured_output: false
---
# system
You are a helpful assistant.

# user
Classify this consumer complaint.

Product options:
{{products}}

Issue options:
{{issues}}

Return JSON with the keys "product", "issue" and "resumo_pt" (a short summary in Portuguese).

Complaint:
{{text}}

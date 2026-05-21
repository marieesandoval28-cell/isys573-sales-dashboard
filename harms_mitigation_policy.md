# Harms Mitigation Policy

This policy reduces risks when using AI agents in the dashboard workflow.

## Risks
- prompt injection
- hallucinated code
- unsafe or insecure code
- copied protected material
- private data exposure
- bypassing human review

## Controls
- Keep project boundaries in AGENTS.md
- Use human review before accepting AI changes
- Run tests before merging
- Check generated code for security risks
- Do not allow AI to access passwords, keys, or private data
- Use version control so changes can be traced and reversed

## Prompt Shields
Prompt shields block malicious or unsafe prompts before they reach the AI agent.

## Groundedness Detection
Groundedness detection checks that AI answers are based on the actual project files.

## Protected Material Detection
Protected material detection checks that AI does not copy copyrighted or private content.
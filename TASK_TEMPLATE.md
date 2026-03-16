# AutoSocial.tech Task Template

## Goal
- State the product outcome in one or two lines.

## Current Behavior
- Describe the exact current runtime behavior.
- Include real files, routes, and screens where relevant.

## Desired Behavior
- Describe the end state precisely.
- Distinguish UI expectations from backend/runtime expectations.

## Constraints
- Preserve backward compatibility.
- Keep API contracts stable unless explicitly authorized to change them.
- Do not break auth, billing, plans, publishing, onboarding, dashboard, create flow, or generation flows.
- Prefer minimal targeted edits over broad refactors.
- Do not reactivate deprecated GPT image generation or other legacy runtime paths.

## Allowed File Scope
- List the intended files.
- If the task can be solved in `1-3` files, keep it there.
- Expanding scope requires justification tied to a concrete dependency or regression risk.

## Definition Of Done
- Runtime behavior matches desired behavior.
- Adjacent critical domains still work.
- Verification completed with concrete checks.
- Response includes exact files changed and exact validations performed.

## Required Response Format
1. Solution summary
2. Files changed
3. Key implementation notes
4. Verification performed
5. Risks or assumptions

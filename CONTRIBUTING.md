# Contributing to Txori Kantua

`main` is the stable branch. Create `feature/...`, `fix/...` or `docs/...` from an up-to-date copy of main, link an issue and keep PRs small with a coherent result. Use descriptive commits; each member uses their own account.

1. Review criteria, dependencies and hardware status. Select work in planning and update the Project.
2. Implement with logic/contract tests and physical evidence where applicable; document versions and limits.
3. Open a PR with context, validation and references. Use `Closes #N` only when the PR completes all criteria; for partial progress, `Refs #N`.
4. Request review from another member. Resolve comments before merging; do not self-approve or mark Done with pending tests.
5. After integration, check the actual status and close the issue if the evidence satisfies the scope. Update documentation and the Project.

Avoid direct commits to main when a reasonable alternative exists. No rules requiring non-existent checks are enabled. Since 06/11/2026, main requires one approval from another member and resolved conversations; new changes invalidate previous approvals. Force-push and deletion of main are not allowed. There are no mandatory CI checks yet. The administrator keeps the ability to make exceptions for recovery, but must follow the PR and review flow for normal work.

## Configuration, data and quality

- Never commit real `.env` files, tokens, keys, database copies or recordings. A future `.env.example` will contain only names and dummy values.
- Do not install packages globally or assume versions: use a virtual environment and pin dependencies that have been tested on the Pi 5.
- Separate physical adapters from logic; validate JSON at the boundaries and handle network/peripheral failures.
- Structured logs with identifiers and without audio, credentials or personal data.
- An incompatible contract change requires a new version and a migration plan; agree it with all consumers.
- Do not invent test results. Document what was run, where, with which commit and what is missing.

There is no software suite or official test command yet. Each PR that adds code will introduce its reproducible verification; the CI issue will consolidate automation. Do not add empty Python files to give the appearance of implementation.

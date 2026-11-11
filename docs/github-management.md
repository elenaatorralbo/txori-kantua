# GitHub configuration and pending items

## Initial audit · 05/11/2026

Existing public repository: [elenaatorralbo/txori-kantua](https://github.com/elenaatorralbo/txori-kantua). Single `main` branch, initial commit `be33ac6`, README with a title; no issues, milestones, PRs, releases or protection rules. The default labels and the collaborators were kept. The local `.idea/` folder was not modified and is ignored.

There was an untitled personal Project, number 1, not linked to this repository; it was left untouched. No additional repository was created.

## Management created

[Txori Kantua — IoT Development](https://github.com/users/elenaatorralbo/projects/2), public and linked to the repository.

- Status: Backlog, To do, In progress, Review, Done.
- Priority: Critical, High, Medium, Low, in that order.
- Sprint: Iteration field, three official periods (14, 16 and 8 days; review dates also in milestones).
- Area: Hardware, AI, Backend, Frontend, Data, DevOps, Documentation, Testing.
- Assignees: native field; only verified accounts accepted by GitHub. Owner: planned owner (David, Javier, Elena, Erik), filled in for the 34 issues. Start date and Target date filled in for the 32 MVP issues.
- 34 open issues, with no duplicates by title or deliverable; 32 in milestones and 2 optional ones without a sprint commitment. All are added to Backlog.
- 13 labels added: four `priority:*`, eight `area:*` and `optional`; existing labels kept.

| View | Configuration |
|---|---|
| Product Backlog | Table, all issues, Priority ascending according to option order |
| Kanban | Board, Status columns |
| Sprint 1 | Board, `sprint:"Sprint 1"`, Status columns |
| Sprint 2 | Board, `sprint:"Sprint 2"`, Status columns |
| Sprint 3 | Board, `sprint:"Sprint 3"`, Status columns |
| My Tasks | Table, `assignee:@me` |
| Javier | Table, `owner:Javier`; ten tasks, also assigned to javiers2004 |
| Roadmap | Timeline, excludes `label:optional`; dates on the items |

Milestones: [Foundations](https://github.com/elenaatorralbo/txori-kantua/milestone/1), 17/11/2026; [Working Pipeline](https://github.com/elenaatorralbo/txori-kantua/milestone/2), 03/12/2026; [MVP Release](https://github.com/elenaatorralbo/txori-kantua/milestone/3), 11/12/2026. The API records 22:59:59 UTC, equivalent to the end of the day in Europe/Madrid for these dates.

## Permissions and limits

The first access to Projects failed because the token lacked `read:project`/`project`. After updating the authorisation, the project could be created and configured. No tokens were stored in files and collaborator permissions were not changed.

Persistent sorting was configured through the REST view-creation endpoint, because the GraphQL view-configuration input only exposed visible fields. Reference: [official GitHub views API](https://docs.github.com/en/rest/projects/views). Only the initial view created during this session was replaced, keeping a single Product Backlog.

**Pending visual adjustment:** open Roadmap → View options → Date fields and confirm `Start date` / `Target date` (or the Sprint field if iterations are preferred). The API used creates the layout and loads the item dates, but does not expose or allow verifying the pair of fields chosen in the interface. It is not claimed that the bars are already configured visually.

Update 06/11/2026: main is protected with one mandatory approval, invalidation of reviews after changes and resolution of conversations. Force-push and deletion are disabled; non-existent CI checks and CODEOWNERS are not required. The administrator keeps a recovery exception (`enforce_admins=false`), maintaining the reviewed-PR rule. The API accepted and returned the configuration. There is no early release or tag.

A personal Project does not automatically inherit all repository write permissions. No collaborators have been added to the Project, to respect the instruction not to modify permissions unnecessarily. The owner can manage the fields; check with the team whether edit access is required before inviting the confirmed accounts in Project → Settings → Manage access. Viewing and assigning issues in the repo is not the same as being able to edit Project fields.

## Wiki

`has_wiki` is enabled, but `git ls-remote https://github.com/elenaatorralbo/txori-kantua.wiki.git` returned "Repository not found". No page has been created or published. The canonical documentation is kept in the repository PR to avoid two diverging copies.

If a Wiki front page is wanted:

1. Open the [Wiki](https://github.com/elenaatorralbo/txori-kantua/wiki) with an account with write access and select **Create the first page**.
2. Create `Home` titled Txori Kantua with links to the README, architecture, hardware, SCRUM, roadmap, MQTT, API and privacy on `main`, once the PR is merged.
3. Add a `_Sidebar` navigation with those same links and a link to the Project.
4. Keep the pages as an index; technical content changes are reviewed through PRs in `docs/`.

## Follow-up of 06/11/2026

PR #35 is merged (commit `aac6515`). Elena confirmed the group of four; it is recorded as a team confirmation. Javier corresponds to the `javiers2004` profile (Javier Santamaría Pascual). After accepting the invitation, the assignability check succeeded and the ten issues #2, #9, #10, #13, #18, #19, #20, #26, #29 and #32 were natively assigned to his account on 06/11/2026. Owner = Javier matches that responsibility.

An attempt was made to configure Roadmap from Dia. The session does not allow running automation JavaScript; the accessibility controls produced no changes and the screenshot failed. Elena indicated that enabling access would require restarting the terminal. Therefore, the item dates are loaded, but the visual selection of fields is still pending. Browser options were not altered and the session was not restarted.

## Real pending items

- Review the documentation follow-up PR; the initial PR #35 is already merged.
- Check the Roadmap date fields in the interface.
- Confirm team availability/capacity and material; no physical test has been run.
- Initialise the Wiki only if it adds value; it does not block the project.
- Review edit access to the Project if the team is going to move cards directly.

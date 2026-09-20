# Your first KPI run

Imagine you are preparing a monthly review. Your tasks are in an issue tracker, estimates
are in a sheet, and the delivery dates changed during the project. You want the numbers,
but you also want notes that explain what actually happened.

KPI Copilot helps your AI assistant do that work. You describe your workflow once, review
what it understood, and ask it to prepare KPIs. You normally work with two things: **your
saved profile** and **your KPI workbook**. The assistant handles the files behind them.

## 1. Choose where you will talk to the assistant

Start in the AI tool you already use. What matters is what that session can access.

| Where you work | What you need before the first run |
|---|---|
| A coding assistant such as Cursor, Codex or a CLI | A local copy of this repository opened in the assistant, with permission to run commands and read your project files |
| A desktop assistant with local MCP support | A one-time connection to KPI Copilot's local runner; ask the assistant or your administrator to follow the [connection guide](03-Prerequisites.md#optional-local-mcp-connection) |
| A browser assistant with a Python/file workspace | The repository archive and exports of the project sources you want it to read; downloadable workbooks are the simplest output |
| A browser chat with no code workspace or connected runner | It can help review a workbook, but it cannot run KPI Copilot yet; use one of the routes above |

You do not need all these tools. Choose one. Installing a skill gives the assistant
instructions; it does not, by itself, give it access to your tracker or a place to run code.
Individual host installation checks are still tracked in the [audit](11-Audit.md).

If you have not installed the tool, send this first:

> Help me get KPI Copilot ready in this AI tool. Use the repository's setup instructions,
> check whether this session can run it, and explain any one-time installation or connection
> step I need to do. Start with a local review workbook.

The [technical setup guide](03-Prerequisites.md) is for the assistant or person doing that
installation. You do not need to learn its commands to prepare KPIs.

## 2. Bring one project and the sources you trust

For your first run, choose a finished period you know well. It is easier to spot a wrong
delivery rule on work you remember than on an unfamiliar project.

Have these ready:

- **The project:** its name, tracker link or export, and the period you want to measure.
- **Your working rules:** hours or story points, what “done” means, and any categories you
  exclude. If you are unsure, the assistant will propose a mapping for you to correct.
- **Extra sources, if needed:** the agreed plan, approved estimates, and a timeline or
  project tracker. A tracker-only workflow is fine when it has the necessary evidence.
- **The destination:** a local workbook, a Google Drive folder, or a dedicated KPI Google
  Sheet. Keep your original project tracker and manual reference workbook separate.

You do not need to reorganize your team's boards or create a new sheet of configuration
before starting. The assistant can map the columns you already use.
If work for this project was delivered on another board, provide those specific task links.
The assistant can include them without searching every project in the account.

## 3. Connect the accounts this project needs

Being signed in to an AI tool does not automatically connect Asana, Jira, GitHub, Google
or PMS. Even a browser login is usable only when the assistant can access **that browser
and profile** through its supported tools.

Ask for a readiness check. The assistant should tell you what already works and offer the
available connection choices before asking you to sign in.

| What you want to use | What needs to be accessible |
|---|---|
| Your issue tracker | A supported existing connection, an approved API connection, or a saved export; Asana also has a signed-in-tab export route |
| Files already on your computer | The assistant's runner must be able to read the folder you select |
| Google Drive sources or a live Google Sheet | Google access for the selected files; an AI connector and the local runner may have separate connections |
| A local `.xlsx` review workbook | No Google login is needed |
| PMS targets or submission | Access to your PMS deployment and selected project; submission requires a supported write route and your approval |

With browser sign-in, you complete the sign-in and consent step yourself. If you choose a
token instead, the assistant explains how to enter it privately. **Do not paste passwords
or tokens into the conversation.** Exported files are a valid starting route when account
connections are unavailable.

## 4. Describe your workflow and let the assistant build the profile

Here is a fictional first message. Replace the bracketed parts with your own details;
leave out any source you do not use.

> Set up KPI Copilot for [project name]. The tracker is [link], and I want KPIs for
> [period]. We estimate in [hours/story points]. Development is finished at [state];
> client handover is recorded in [place].
>
> Use this plan [file/link], approved estimates [file/link], and timeline [file/link].
> For defects, count [your rule] and exclude [your exceptions]. Show me how you will
> count parent tasks, subtasks and separately estimated changes so work is counted once.
>
> Create a local review workbook first. Inspect the available sources, propose my profile
> in plain English, and ask only what you cannot determine. Do not read email or chat.

The assistant now checks access, reads the bounded sources, and describes its proposal.
For example: “Velocity uses story points from accepted tickets. Improvements are listed
but excluded from the defect count. Each approved change is one deliverable. The timeline
supplies actual handover dates.”

Correct anything that does not match your team. A feature-freeze date, the final delivery
deadline and the actual handover date can all be different; say so. An old estimate status
may also need a confirmed correction rather than a guess.

The assistant saves this agreement as your **profile**, outside the repository, and tells
you where it is. You can ask to change it later in ordinary language. The workbook's
**Config** tab shows the counting rules; **Periods** shows the dates and shared effort.
The profile is reusable configuration, not a form you must fill in before every run.

## 5. Review the first result

Once setup is ready, say:

> Prepare KPIs for [project] for [period] using my saved profile. Update the review
> workbook, explain any missed targets from the evidence, and show me what still needs
> my answer. Do not submit to PMS yet.

The assistant reads the tracker in bulk, calculates the measures, and reviews uncertain
classifications together. It should then bring you one short set of questions only you
can answer, such as an actual handover date or whether a change was approved.

Open the workbook and start with:

1. **Dashboard and KPI Summary:** values, targets, and plain-language notes.
2. **Open Questions:** missing facts or decisions that affect the result.
3. **Task and defect registers:** what counted, what was excluded, and evidence links.

Yellow cells are for corrections and explanations. Answer in the conversation or edit
those cells, then ask the assistant to refresh. It reads your edits back before rebuilding
the workbook. A missing fact should say **Not measured** or remain visibly unresolved;
it should never become a guessed zero or a flattering percentage.

A useful note tells you the unit, the relevant count, the exclusions and the actual
reason. For example: “In story points, the team completed 42 of the 50 planned. The export
feature moved to the next cycle after the client changed the required format.” That last
sentence belongs there only when the sources support it.

## 6. Choose how the results leave the review

You can keep the `.xlsx`, ask for a dedicated Google Sheet updated in place, or copy the
reviewed values into PMS yourself. If you choose Google Sheets, the assistant first checks
the connection and confirms the destination. A reference workbook is a reference, not the
output to replace.

When you want the assistant to submit, ask:

> Show me the final values and notes for [project and period] that you would send to PMS.

After reviewing that preview, explicitly approve it in the conversation. The assistant
submits through the available supported route and reads the saved values back. If the
inputs change, it must show you the changed result before submission. A successful local
workbook is not proof that PMS or Google Sheets was updated.

## 7. Next month, start with one sentence

> Refresh KPIs for [project] for [period] using my saved profile and update the same workbook.

You should not repeat the setup interview. Stable evidence and earlier decisions are
reused; changed cards and new questions get attention. To add another project, say what it
shares with the first and what differs. One project can use hours and another story points.

To change a rule, be specific:

> For this project, include existing bugs from the next period onward. Show me the effect
> before saving that change to my profile.

## Keeping a run quick

**A routine refresh should take minutes, not half an hour of opening cards.** This is the
product goal, not a promised time for every board. Connection setup, a changed plan PDF,
provider limits, assistant review and waiting for your answers add time.

The normal route reads the tracker in bulk, reuses unchanged history where the reader
supports it, remembers judgements, and digests a document only when it changes. Signed-in
browser exports currently read the full configured board; API caching can make repeated
reads faster. Email and chat are searched only when you explicitly request a focused check.

If a run drags, say:

> Show what is taking time: source reading, calculation, review or publishing. Reuse the
> current snapshot for judgement and recalculation. Do not re-read unchanged sources or
> open cards one by one. Give me the draft and the unresolved questions together.

The assistant should report both the measured processing time and any unfinished review
or delivery work. A fast calculation alone is not a fast completed KPI run.

For more examples, see [setup prompts](10-Setup-By-Conversation.md). For everyday corrections,
see [daily use](04-Daily-Use.md). Installation and troubleshooting live in the
[technical setup guide](03-Prerequisites.md).

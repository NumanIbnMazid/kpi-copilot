# Every profile field

Generated from `plugin/kpi-copilot/schemas/profile.schema.json` by `scripts/gen_reference.py`. Do not edit by hand — change the schema and regenerate, or the two disagree within a release.

This is the exhaustive list. The documents beside it explain *why* and *when* for the parts that need judgement; come here when you want to know whether a field exists and exactly what it takes.

You can also ask for one setting at a time, which is usually faster:

```bash
python3 scripts/profile_tool.py explain --key workflow.delivered_when
```

**Required** marks a field the schema insists on. Almost nothing is required — the tool would rather report a gap than refuse to run.

## `profile_version`

Type: `1.0`.

## `owner`

| Field | Type | Default | Required | What it is |
|---|---|---|---|---|
| `name` | string |  | yes |  |
| `email` | string |  |  |  |
| `role` | string |  |  | e.g. Software Project Lead |
| `account` | string |  |  | e.g. Northwind. Used to name output folders. |
| `timezone` | string | `Asia/Dhaka` |  | Dates in notes are written in this timezone. |

## `organization`

| Field | Type | Default | Required | What it is |
|---|---|---|---|---|
| `pms_base_url` | string | `https://pms.example.com` | yes |  |
| `kpi_registry` | string | `kpi_registry.json` |  | Local cache of the KPI definitions read from PMS: ids, names, the official descriptions, the default targets, and the targets each project sets for itself. Refreshed by scripts/kpi_registry.py --refresh. Never hand-edited - a target changed in PMS is picked up by the next refresh, and a target changed here would make the workbook and PMS disagree. |
| `note_format` | string | `what is measured || the numbers || what was left out || why` |  | Fixed company-wide so management reads every project the same way. |
| `evidence_required` | boolean | `yes` |  | Yes = a Yes/No with no link is flagged in review. |

## `tools`

The tool registry: every place your projects' truth lives, with a plain-language note on what it is for. One registry covers all your projects - list the Google Chat space for one account and the Slack channel for another, and tag each with the projects it belongs to. A tool with no projects listed is available to all of them (PMS, your Drive folder). This is what lets Claude find things without being told each time, and what lets a new team member understand the setup at a glance.

| Field | Type | Default | Required | What it is |
|---|---|---|---|---|
| `id` | string |  | yes | Short handle used elsewhere in the profile, e.g. 'tracker', 'chat-devqa', 'plan-doc'. |
| `kind` | one of: `issue-tracker`, `chat`, `email`, `doc-store`, `spreadsheet`, `document`, `wiki`, `pms`, `time-tracking`, `ci`, `other` |  | yes | What sort of thing it is. Drives which steps can use it. |
| `name` | string |  | yes | What people call it, e.g. 'Asana', 'Northwind Dev-QA'. |
| `url_or_id` | string |  |  | Link, space id, sheet id or folder id. |
| `description` | string |  |  | One sentence: what this is and why it matters. Written for a person who has never seen the project. |
| `used_for` | list, any of: `scope`, `estimates`, `dates`, `defects`, `evidence`, `handover`, `status`, `timeline`, `output`, `approval` |  |  | Which parts of a KPI run read or write this. |
| `access` | string |  |  | How to get in, e.g. 'Google SSO', 'Atlassian account'. Never a credential. |
| `projects` | list of string |  |  | Project ids this tool belongs to. Leave empty when it applies to all of them, such as PMS or a shared Drive folder. |
| `accounts` | list of string |  |  | Account ids this tool belongs to. A Google Chat space for one client and a Slack channel for another live side by side here, each tagged with its account. |
| `people` | list of string |  |  | Who is in this space or owns this document, as their names appear in it. Optional, but it is how somebody new to the account finds out who to ask, and it is what lets a run tell a client-reported defect from a QA-reported one when the tracker does not say. |
| `client_facing` | boolean | `no` |  | Is the client in here. A client-facing space is where agreed dates get set and where a client-found defect first appears; an internal one is not. Marking it wrong is how a date somebody agreed in a client call gets treated as an internal decision. |
| `note` | string |  |  | Anything else worth knowing: quirks, when it is quiet, what NOT to trust in it. |

## `tracker`

| Field | Type | Default | Required | What it is |
|---|---|---|---|---|
| `adapter` | string |  | yes | Which adapter turns your tracker into KIF. Ships with: asana, jira, csv. 'csv' works with any tracker that can export - use it on day one and write a native adapter later if the manual export gets tiring. |
| `project_ref` | string |  |  | Asana: the number after /project/. Jira: the project key, e.g. SAV. |
| `url` | string |  |  |  |
| `estimate_field` | string | `Estimated Time` |  |  |
| `story_point_field` | string |  |  | Leave blank if you measure in hours. |
| `key_field` | string |  |  | Leave blank to use the tracker's own id. |
| `options` | object |  |  | Adapter-specific extras. See the adapter's own README. |

## `conventions`

How your team names and shapes things. These are regular expressions or literal lists - the setup interview proposes them by looking at your board, and you correct what it got wrong.

| Field | Type | Default | Required | What it is |
|---|---|---|---|---|
| `key_pattern` | string |  |  | Regex, e.g. TKT-\d+ or [A-Z]+-\d+. Blank = use the tracker id. |
| `defect_pattern` | string |  |  | Regex on the title, e.g. ^(Bug\|Observation\|Improvement) ?\d+ - or leave blank and use defect_by below. |
| `defect_by` | one of: `title-pattern`, `issue-type`, `label`, `separate-board`, `field` | `title-pattern` |  | title-pattern \| issue-type \| label \| separate-board \| field |
| `defect_values` | list of string |  |  | e.g. Bug, Defect - used when marked by issue type, label or field. |
| `observation_values` | list of string |  |  | Reported, but not counted as defects by default. |
| `exclude_patterns` | list of string |  |  | Cards that are not deliverables: QA admin cards, milestone markers, grouping/umbrella cards, duplicates. |
| `cr_marker` | string |  |  | Regex, label or field value. Blank = CRs come from the estimates source instead. |
| `client_names` | list of string |  |  | Exact names as they appear in the tracker. Used to tell a client-found defect from a QA-found one. |

## `workflow`

What your team's states mean. This is the single most important section: it is what turns 'our board has a column called In Test' into a number management can compare across projects.

| Field | Type | Default | Required | What it is |
|---|---|---|---|---|
| `delivered_when` | object |  |  | Your delivery event: when an item counts as delivered. Velocity counts items that reached it, and it is the default meaning of 'delivered on time' for a commitment. Most teams set this to the state that means development is finished and testing can start, but it is your choice - name the state, not a convention borrowed from somebody else's board. |
| &nbsp;&nbsp;`delivered_when.signal` | one of: `status-entered`, `label-added`, `field-set`, `closed`, `manual` | `status-entered` |  |  |
| &nbsp;&nbsp;`delivered_when.values` | list of string |  |  | e.g. ['Ready for QA', 'In Test', 'Dev Complete']. First entry into any of these. |
| &nbsp;&nbsp;`delivered_when.from_date` | string |  |  | Apply this rule only from a date onward, when the team changed its process mid-project. Before it, the fallback below applies. |
| &nbsp;&nbsp;`delivered_when.fallback_values` | list of string |  |  |  |
| `closed_when` | object |  |  |  |
| &nbsp;&nbsp;`closed_when.values` | list of string |  |  | e.g. ['Closed', 'Done']. |
| &nbsp;&nbsp;`closed_when.completed_flag_means` | string |  |  | What the tracker's own 'complete' flag means on your board - on some boards it means merged, not accepted. |
| `reopened_when` | object |  |  | Rework Rate = items that were closed and then reopened. A QA fail while the item is still being tested for the first time is normal testing, not rework. |
| &nbsp;&nbsp;`reopened_when.values` | list of string |  |  | States that mean 'back in play after being closed'. |
| &nbsp;&nbsp;`reopened_when.ignore_first_qa_fail` | boolean | `yes` |  |  |
| `clarification_when` | object |  |  | Task Comprehension = the requirement was understood without going back to the client. This is how we detect 'we had to ask'. |
| &nbsp;&nbsp;`clarification_when.values` | list of string |  |  | e.g. ['Awaiting Feedback', 'Blocked - Client']. |
| &nbsp;&nbsp;`clarification_when.also_comments` | boolean | `yes` |  | Also treat a comment asking the client to clarify expected behaviour as 'had to ask'. |
| &nbsp;&nbsp;`clarification_when.exclude_reasons` | list of string | `['build', 'environment', 'access']` |  | Going to Awaiting Feedback for a build or environment dependency is not a comprehension problem. |
| `commitment` | object |  |  | What a team commitment is, and what counts as meeting one. Delivery Commitment measures the reliability of the team: of the things the team negotiated and promised, how many landed on time. Both halves of that need saying, because teams commit to different things and not every task carries a commitment. |
| &nbsp;&nbsp;`commitment.scope` | one of: `committed-only`, `all-deliverables` | `committed-only` |  | committed-only = count just the items the team negotiated a date for, which is what PMS asks for. all-deliverables = treat every item as committed, for a team that commits to the whole scope as one. Items left out are named in the note either way. |
| &nbsp;&nbsp;`commitment.met_when` | string | `delivery` |  | What delivering a commitment means for this team, written as a short phrase that goes into the note. 'delivery' uses your delivery event above; 'handover' means the period's build reached the client; 'completion' means the item was closed. Anything else is used as written, so 'the demo environment was updated' is fine if that is what was promised. |

## `sources`

Where scope, hours and dates come from, and which of them the run is allowed to believe. All optional - a team with none of these still gets KPIs, with the gaps stated plainly.

| Field | Type | Default | Required | What it is |
|---|---|---|---|---|
| `mode` | one of: `tracker-only`, `tracker-first`, `multi-source` | `tracker-first` |  | Which sources may answer a question. tracker-only: the issue tracker is the single source of truth and nothing else is opened, so a run is fast, cheap and reproducible; anything the tracker cannot answer comes back 'Not measured' with the reason. tracker-first: the tracker answers, and the other sources are consulted only for facts it left blank. multi-source: other sources are read even when the tracker has an answer, and a disagreement is reported. |
| `plan` | object |  |  |  |
| &nbsp;&nbsp;`plan.tool_id` | string |  |  |  |
| &nbsp;&nbsp;`plan.kind` | one of: `pdf`, `sheet`, `wiki`, `tracker`, `none` |  |  |  |
| &nbsp;&nbsp;`plan.ref` | string |  |  |  |
| &nbsp;&nbsp;`plan.note` | string |  |  |  |
| `estimates` | object |  |  |  |
| &nbsp;&nbsp;`estimates.tool_id` | string |  |  |  |
| &nbsp;&nbsp;`estimates.kind` | one of: `sheet`, `tracker`, `none` |  |  |  |
| &nbsp;&nbsp;`estimates.ref` | string |  |  |  |
| &nbsp;&nbsp;`estimates.note` | string |  |  |  |
| `timeline` | object |  |  |  |
| &nbsp;&nbsp;`timeline.tool_id` | string |  |  |  |
| &nbsp;&nbsp;`timeline.kind` | one of: `sheet`, `wiki`, `tracker`, `none` |  |  |  |
| &nbsp;&nbsp;`timeline.ref` | string |  |  |  |
| &nbsp;&nbsp;`timeline.note` | string |  |  |  |
| `evidence_channels` | list of string |  |  | tool ids of the chat spaces, mailboxes or threads searched for dates, handovers and decisions. |
| `hours_first` | one of: `plan`, `tracker` | `tracker` |  | plan \| tracker |
| `hours_basis` | one of: `dev`, `dev+qa` | `dev` |  | dev = development hours only. dev+qa = adds each item's QA hours once its QA is done. |

## `scan`

How far a run is allowed to reach. Without limits every refresh re-reads every board, every channel and every thread from the beginning, which is slow, expensive and no more accurate. Every limit has a working default, and whatever a limit cut off is named in the run's Gaps rather than dropped quietly.

| Field | Type | Default | Required | What it is |
|---|---|---|---|---|
| `window` | one of: `period`, `period+grace`, `days`, `all` | `period+grace` |  | The time range a run reads. 'period' is the period's own start and end. 'period+grace' adds grace_days either side, which is what catches a handover announced the morning after the period closed. 'days' uses the 'days' field. 'all' removes the limit. |
| `grace_days` | integer | `14` |  | Used when the range is period+grace. |
| `days` | integer | `90` |  | Used when the range is 'days'. |
| `tracker_scope` | one of: `period`, `touched-since`, `all` | `all` |  | How much of the board to read. 'all' is right for most boards and is the default, because a board is usually small and its history is what proves a date. 'touched-since' reads only items modified inside the window, which is what makes a big long-running board affordable. 'period' reads only items assigned to the period. |
| `comments` | one of: `always`, `on-demand`, `never` | `on-demand` |  | Ticket comments are the most expensive thing on a board and are usually needed for a handful of items. 'on-demand' reads them only for items whose judgement actually depends on one, such as a clarification or a disputed date. |
| `chat` | object |  |  | Limits on chat spaces. Ignored entirely when the source of truth is tracker-only. |
| &nbsp;&nbsp;`chat.lookback_days` | integer | `45` |  |  |
| &nbsp;&nbsp;`chat.max_messages_per_channel` | integer | `300` |  |  |
| &nbsp;&nbsp;`chat.only_when_missing` | boolean | `yes` |  | Search a chat space only for a fact no other source could answer. |
| `mail` | object |  |  | Limits on mailboxes and threads. Ignored when the source of truth is tracker-only. |
| &nbsp;&nbsp;`mail.lookback_days` | integer | `45` |  |  |
| &nbsp;&nbsp;`mail.max_threads` | integer | `50` |  |  |
| `stop_when_found` | boolean | `yes` |  | Stop looking for a fact once a source has answered it, instead of collecting every mention. |
| `max_sources_per_fact` | integer | `2` |  | Raise it only where two sources routinely disagree and you want both quoted. |

## `periods`

How this team slices a project for PMS.

| Field | Type | Default | Required | What it is |
|---|---|---|---|---|
| `model` | one of: `Milestone`, `Delivery cycle`, `Sprint`, `Month`, `Quarter`, `Full project` | `Delivery cycle` |  |  |
| `naming` | string | `Initial Scope, Additional Requests N, Milestone N, Full Project` |  | PMS allows 25 characters. |
| `client_check_default` | one of: `Handover`, `Delivery` | `Handover` |  | Handover = when the build reached the client. Delivery = when the item itself was delivered. |

## `policy`

Counting choices the company allows a team to make. Everything not listed here is fixed by the engine and cannot be varied - that is deliberate.

| Field | Type | Default | Required | What it is |
|---|---|---|---|---|
| `count_observations` | boolean | `no` |  |  |
| `count_improvements` | boolean | `no` |  |  |
| `count_pre_existing` | boolean | `no` |  |  |
| `count_post_release` | boolean | `yes` |  |  |
| `count_rejected` | boolean | `no` |  | Fixed at No. Rejected reports are not defects. |

## `output`

What the run produces and how far it is allowed to go on its own. This is the setting most likely to differ between two leads, and it is deliberately easy to change.

| Field | Type | Default | Required | What it is |
|---|---|---|---|---|
| `mode` | one of: `review-only`, `dry-run`, `assisted-push`, `auto-push` | `assisted-push` | yes | review-only = build the workbook and a copy-paste block; never touch PMS. dry-run = also compute the PMS payload and show the diff, but never write. assisted-push = dry run, then push after an explicit yes in chat. auto-push = push without asking; only honoured when unattended is true, and every push is still logged. |
| `unattended` | boolean | `no` |  | Only meaningful with auto-push. Leave No unless you have run this for a while. |
| `workbook` | one of: `google-sheets`, `xlsx`, `none` | `xlsx` |  |  |
| `workbook_location` | string |  |  | Drive folder id, SharePoint path or a local folder. |
| `workbook_template` | string |  |  | Sheet id or path. Blank = build a fresh one. |
| `run_folder` | string | `runs` |  |  |
| `notify` | string |  |  | A tool id from the Tools tab, or blank for none. |

## `custom_instructions`

Your own instructions, which take precedence over the tool's defaults. Three tiers, and the difference matters: STYLE is free - say how you want things worded and it is followed. RULE OVERRIDES are allowed but recorded - they describe a fact about your project that the defaults get wrong, and each one is printed in the run summary and the workbook so a reader can see the number was produced under a local rule. PMS-OWNED settings are not set here: targets are configurable per project in PMS, so a project that needs a different bar gets one there and the next run reads it; keeping a target in this file instead would make the workbook and PMS disagree about the same number. The KPI ids and the definition of each ratio are fixed, because the counting is what makes two projects comparable. An attempt to set either here is reported, not silently dropped.

| Field | Type | Default | Required | What it is |
|---|---|---|---|---|
| `notes_style` | string |  |  | How you want the 'why' text to read. Free text. Example: 'Keep it under two sentences. Name the ticket, not the person. British spelling.' |
| `always` | list of string |  |  | Things to do on every run. Example: 'Always show the previous period next to the new one.' 'Always flag a KPI that moved more than 20 points.' |
| `never` | list of string |  |  | Things never to do. Example: 'Never post to the team chat.' 'Never push on a Friday.' |
| `glossary` | list of string |  |  | Words your team uses that an outsider would misread. Example: 'Handover means the client build, not the internal release.' 'MK = PartnerSync integration.' |
| `rule_overrides` | list of objects |  |  | Project facts the defaults get wrong. Each is applied and then printed in the run summary, so nobody has to guess why a number differs from the standard reading. |
| &nbsp;&nbsp;`rule_overrides[].rule` | one of: `delivered_signal`, `client_date_source`, `commit_date_source`, `cr_denominator`, `exclude_key`, `include_key`, `defect_phase`, `hours_source`, `period_of_key`, `velocity_team_hours` |  | yes | Which behaviour to change. Supported: delivered_signal, client_date_source, commit_date_source, cr_denominator, exclude_key, include_key, defect_phase, hours_source, period_of_key, velocity_team_hours. |
| &nbsp;&nbsp;`rule_overrides[].value` | string |  | yes | The new value, or 'KEY = value' when the rule is about one ticket. |
| &nbsp;&nbsp;`rule_overrides[].why` | string |  | yes | Required. It appears in the run summary, so write it for somebody who was not in the room. |
| &nbsp;&nbsp;`rule_overrides[].approved_by` | string |  |  | Who agreed to it. Leave blank for a decision that is yours alone to make. |
| &nbsp;&nbsp;`rule_overrides[].expires` | string |  |  | Optional date after which the run warns that this override may be stale. |
| `escalation` | string |  |  | What to do when something needs a decision you cannot make. Example: 'Ask me in chat; if I do not answer in a day, hold the run and do not push.' |

## `accounts`

Your client accounts. Most of what varies between two projects actually varies between two clients - Northwind on Asana and Google Chat, Acme on Jira and Slack - so say it once here and every project on that account inherits it. A lead with one account can leave this out entirely.

| Field | Type | Default | Required | What it is |
|---|---|---|---|---|
| `id` | string |  | yes | Short handle, e.g. 'northwind'. Projects point at it. |
| `name` | string |  |  | What people call the client. |
| `notes` | string |  |  | Anything a newcomer to this account should know. |
| `overrides` | object |  |  | What is true for every project on this account, but not for your others. Set the tracker, the chat spaces and the conventions here rather than repeating them on each project. |
| &nbsp;&nbsp;`overrides.tracker` | object |  |  | A different tracker or adapter. |
| &nbsp;&nbsp;`overrides.conventions` | object |  |  | Different ticket, defect or exclusion conventions. |
| &nbsp;&nbsp;`overrides.workflow` | object |  |  | Different state names. The most common override after tracker. |
| &nbsp;&nbsp;`overrides.sources` | object |  |  | A different plan, estimates sheet or evidence channels. |
| &nbsp;&nbsp;`overrides.periods` | object |  |  | A different period model or velocity unit. |
| &nbsp;&nbsp;`overrides.policy` | object |  |  | Different counting choices, where the company allows them. |
| &nbsp;&nbsp;`overrides.output` | object |  |  | A different output mode or working-file location. |
| &nbsp;&nbsp;`overrides.custom_instructions` | object |  |  | House style or rule overrides for this scope only. |

## `projects`

The projects this profile covers - one row per PMS project. Everything above is the default for all of them; a project that differs says so in its 'overrides'. One profile can cover several accounts on several trackers.

| Field | Type | Default | Required | What it is |
|---|---|---|---|---|
| `id` | string |  | yes | Short handle, e.g. 'q3-release'. Names the config and run files. |
| `name` | string |  | yes |  |
| `pms_project_id` | integer |  |  |  |
| `tracker_ref` | string |  |  | Board id / project key for this project, when it differs from the tracker default. |
| `workbook_ref` | string |  |  | Sheet id or file path of this project's tracker workbook. |
| `plan_ref` | string |  |  |  |
| `estimates_ref` | string |  |  |  |
| `period_model` | string |  |  |  |
| `velocity_unit` | one of: `Estimated Hours`, `Story Points` |  |  |  |
| `notes` | string |  |  |  |
| `overrides` | object |  |  | What differs for this one project, on top of its account. Usually empty - if you find yourself repeating the same override on several projects, it belongs on the account instead. |
| &nbsp;&nbsp;`overrides.tracker` | object |  |  | A different tracker or adapter. |
| &nbsp;&nbsp;`overrides.conventions` | object |  |  | Different ticket, defect or exclusion conventions. |
| &nbsp;&nbsp;`overrides.workflow` | object |  |  | Different state names. The most common override after tracker. |
| &nbsp;&nbsp;`overrides.sources` | object |  |  | A different plan, estimates sheet or evidence channels. |
| &nbsp;&nbsp;`overrides.periods` | object |  |  | A different period model or velocity unit. |
| &nbsp;&nbsp;`overrides.policy` | object |  |  | Different counting choices, where the company allows them. |
| &nbsp;&nbsp;`overrides.output` | object |  |  | A different output mode or working-file location. |
| &nbsp;&nbsp;`overrides.custom_instructions` | object |  |  | House style or rule overrides for this scope only. |
| `account` | string |  |  | The account this project belongs to, by id. It inherits that account's overrides. |

## `learned`

Settings captured from conversation, each with the sentence it came from. Written by scripts/remember.py, never by hand. It answers 'why is this set like this' six months later, which is the question a configuration file normally cannot answer.

| Field | Type | Default | Required | What it is |
|---|---|---|---|---|
| `at` | string |  |  | When it was captured. |
| `setting` | string |  |  | The dotted path, or tools[<id>]. |
| `scope` | string |  |  | profile defaults, or the account or project it applies to. |
| `before` |  |  |  | What it was. |
| `after` |  |  |  | What it became. |
| `why` | string |  |  | The sentence it came from. |
| `by` | string |  |  | Who asked. |


/* Asana board, from a signed-in tab, for people who cannot create an access token.
 *
 * Paste into the console of an app.asana.com tab (or have an assistant's browser tool run
 * it), then call:
 *
 *     kpiSnapshot('1200000000000001')
 *
 * It reads the board through Asana's own API with the page's session, so there is no token,
 * and it DOWNLOADS the result as asana-raw-<project>.json. That last part matters: the file
 * goes to disk, not through a chat window. Carrying a board back through an assistant's
 * context is what used to make a run take half an hour.
 *
 * It makes no judgements and reshapes nothing - these are Asana's raw responses. Turning
 * them into a board snapshot happens in api.py (--from-raw), the same code the token route
 * uses, so both routes produce the same thing.
 */
(function () {
  const API = '/api/1.0';
  const TASK_FIELDS = 'name,notes,completed,completed_at,created_at,modified_at,due_on,start_on,' +
    'assignee.name,created_by.name,memberships.project.gid,memberships.section.name,tags.name,' +
    'custom_fields.name,custom_fields.display_value,custom_fields.number_value,' +
    'custom_fields.enum_value.name,parent.gid,num_subtasks,permalink_url,resource_subtype';
  const STORY_FIELDS = 'created_at,created_by.name,resource_subtype,type,text,old_section.name,' +
    'new_section.name,custom_field.name,old_enum_value.name,new_enum_value.name';

  async function get(url) {
    for (let attempt = 0; attempt < 6; attempt++) {
      const r = await fetch(url, { credentials: 'include', headers: { accept: 'application/json' } });
      if (r.status === 429 || r.status >= 500) {
        await new Promise(ok => setTimeout(ok, 1000 * (Number(r.headers.get('Retry-After')) || 2 ** attempt)));
        continue;
      }
      if (!r.ok) throw new Error(`${r.status} ${url}`);
      return r.json();
    }
    throw new Error(`rate limited: ${url}`);
  }

  async function pages(url) {
    const out = [];
    let u = url;
    for (let guard = 0; u && guard < 500; guard++) {
      const j = await get(u);
      out.push(...(j.data || []));
      u = j.next_page ? j.next_page.uri : null;
    }
    if (u) throw new Error('Pagination exceeded 500 pages; no incomplete export was saved.');
    return out;
  }

  async function pool(items, n, fn) {
    let i = 0;
    await Promise.all(Array.from({ length: n }, async () => {
      while (i < items.length) { const k = i++; await fn(items[k]); }
    }));
  }

  window.kpiSnapshot = async function (projectGid, { includeSubtasks = false, linkedTaskIds = [] } = {}) {
    if (!Array.isArray(linkedTaskIds) || linkedTaskIds.some(id => !/^[0-9]+$/.test(String(id))))
      throw new Error('linkedTaskIds must be a list of explicitly configured Asana task IDs.');
    const project = (await get(`${API}/projects/${projectGid}?opt_fields=name,permalink_url`)).data;
    const sections = await pages(`${API}/projects/${projectGid}/sections?opt_fields=name&limit=100`);
    let tasks = await pages(`${API}/tasks?project=${projectGid}&limit=100&opt_fields=${TASK_FIELDS}`);
    if (includeSubtasks) {
      const seen = new Map(tasks.map(t => [t.gid, t]));
      const visited = new Set();
      let pending = tasks.filter(t => t.num_subtasks);
      while (pending.length) {
        const batch = pending.filter(t => !visited.has(t.gid));
        batch.forEach(t => visited.add(t.gid));
        pending = [];
        await pool(batch, 8, async t => {
          for (const child of await pages(`${API}/tasks/${t.gid}/subtasks?limit=100&opt_fields=${TASK_FIELDS}`)) {
            seen.set(child.gid, child);
            if (child.num_subtasks && !visited.has(child.gid)) pending.push(child);
          }
        });
        if (seen.size > 10000) throw new Error('Subtask expansion exceeds 10000 cards; narrow the project scope.');
      }
      tasks = [...seen.values()];
    }
    const seenTasks = new Map(tasks.map(t => [t.gid, t]));
    await pool([...new Set(linkedTaskIds.map(String))].filter(id => !seenTasks.has(id)), 8, async id => {
      const task = (await get(`${API}/tasks/${id}?opt_fields=${TASK_FIELDS}`)).data;
      if (String(task?.gid) !== id) throw new Error('Linked task response does not match the request.');
      seenTasks.set(id, task);
    });
    tasks = [...seenTasks.values()];
    const stories = {};
    await pool(tasks, 8, async t => {
      stories[t.gid] = await pages(`${API}/tasks/${t.gid}/stories?limit=100&opt_fields=${STORY_FIELDS}`);
    });
    const raw = { project, sections, tasks, stories, subtasks_expanded: includeSubtasks,
      fetched_at: new Date().toISOString() };
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(raw)], { type: 'application/json' }));
    a.download = `asana-raw-${projectGid}.json`;
    // A visible retry link supplies a user gesture when automatic downloads are blocked.
    const previous = document.getElementById('kpi-snapshot-download');
    if (previous) { URL.revokeObjectURL(previous.href); previous.remove(); }
    a.id = 'kpi-snapshot-download';
    a.textContent = `Save KPI board export (${tasks.length} cards)`;
    a.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:2147483647;padding:16px;' +
      'background:#16324f;color:white;border-radius:8px;font:16px sans-serif';
    document.body.appendChild(a);
    a.click();
    return `Download requested for ${tasks.length} cards as ${a.download}. Verify the file was saved before importing; use the Save KPI board export link if needed. Reload the page to remove the link.`;
  };
})();

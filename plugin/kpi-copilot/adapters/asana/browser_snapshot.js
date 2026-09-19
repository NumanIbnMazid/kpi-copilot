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
    for (let u = url, guard = 0; u && guard < 500; guard++) {
      const j = await get(u);
      out.push(...(j.data || []));
      u = j.next_page ? j.next_page.uri : null;
    }
    return out;
  }

  async function pool(items, n, fn) {
    let i = 0;
    await Promise.all(Array.from({ length: n }, async () => {
      while (i < items.length) { const k = i++; await fn(items[k]); }
    }));
  }

  window.kpiSnapshot = async function (projectGid) {
    const project = (await get(`${API}/projects/${projectGid}?opt_fields=name,permalink_url`)).data;
    const sections = await pages(`${API}/projects/${projectGid}/sections?opt_fields=name&limit=100`);
    const tasks = await pages(`${API}/tasks?project=${projectGid}&limit=100&opt_fields=${TASK_FIELDS}`);
    const stories = {};
    await pool(tasks, 8, async t => {
      stories[t.gid] = await pages(`${API}/tasks/${t.gid}/stories?limit=100&opt_fields=${STORY_FIELDS}`);
    });
    const raw = { project, sections, tasks, stories, fetched_at: new Date().toISOString() };
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(raw)], { type: 'application/json' }));
    a.download = `asana-raw-${projectGid}.json`;
    a.click();
    return `${tasks.length} cards saved to your Downloads folder as ${a.download}`;
  };
})();

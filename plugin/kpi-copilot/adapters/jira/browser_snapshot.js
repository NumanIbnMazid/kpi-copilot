/* Jira project, from a signed-in tab, for people who cannot create an API token.
 *
 * Paste into the console of a tab on your Jira site (or have an assistant's browser tool run
 * it), then call:
 *
 *     kpiSnapshot('project = ACME')            // any JQL
 *
 * It reads through Jira's own REST API with the page's session, so there is no token, and it
 * DOWNLOADS the result as jira-raw.json. The file goes to disk, not through a chat window -
 * carrying a board through an assistant's context is what makes a run take half an hour.
 *
 * It makes no judgements and reshapes nothing. adapters/jira/api.py (--from-raw) turns it into
 * a board snapshot with the same code the token route uses, so both routes give the same thing.
 */
(function () {
  const FIELDS = ['summary', 'description', 'status', 'issuetype', 'created', 'updated', 'resolutiondate',
    'resolution', 'assignee', 'reporter', 'creator', 'labels', 'parent', 'comment', 'timeoriginalestimate',
    'priority', 'fixVersions', 'duedate'];

  async function call(url, body) {
    for (let attempt = 0; attempt < 6; attempt++) {
      const r = await fetch(url, {
        method: body ? 'POST' : 'GET', credentials: 'include',
        headers: { accept: 'application/json', 'content-type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (r.status === 429 || r.status >= 500) {
        await new Promise(ok => setTimeout(ok, 1000 * (Number(r.headers.get('Retry-After')) || 2 ** attempt)));
        continue;
      }
      if (!r.ok) { const e = new Error(`${r.status} ${url}`); e.status = r.status; throw e; }
      return r.json();
    }
    throw new Error(`rate limited: ${url}`);
  }

  window.kpiSnapshot = async function (jql) {
    const fields = await call('/rest/api/2/field');
    const points = fields.filter(f => /story points?/i.test(f.name)).map(f => f.id);
    const want = FIELDS.concat(points);
    const issues = [];
    try {                                               // Jira Cloud
      for (let token; ;) {
        const page = await call('/rest/api/3/search/jql',
          { jql, fields: want, expand: 'changelog', maxResults: 100, nextPageToken: token });
        issues.push(...(page.issues || []));
        token = page.nextPageToken;
        if (!token) break;
      }
    } catch (e) {                                       // Server / Data Center
      if (![404, 405, 410].includes(e.status)) throw e;
      for (let start = 0; ;) {
        const q = new URLSearchParams({ jql, fields: want.join(','), expand: 'changelog', maxResults: 100, startAt: start });
        const page = await call(`/rest/api/2/search?${q}`);
        issues.push(...(page.issues || []));
        start += (page.issues || []).length;
        if (!(page.issues || []).length || start >= page.total) break;
      }
    }
    const raw = { site: location.origin, jql, fields, issues, fetched_at: new Date().toISOString() };
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(raw)], { type: 'application/json' }));
    a.download = 'jira-raw.json';
    a.click();
    return `${issues.length} issues saved to your Downloads folder as jira-raw.json`;
  };
})();

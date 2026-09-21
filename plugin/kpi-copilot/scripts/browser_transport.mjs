/* Host driver for the file-backed API transport. Pass already-selected CUA CDP handles.
 * Requests use the current tab's own origin. Session credentials stay in that origin.
 * Asana reads use its ordinary reader, including complete paginated story histories.
 */
export async function drain({directory, fs, clients, origins, limit = 12}) {
  const files = (await fs.readdir(directory)).filter(n => n.endsWith('.request.json'));
  const jobs = [];
  for (const name of files) {
    const response = `${directory}/${name.replace('.request.', '.response.')}`;
    try { await fs.access(response); continue; } catch {}
    const request = JSON.parse(await fs.readFile(`${directory}/${name}`, 'utf8'));
    if (!clients[request.service]) continue;
    if (request.expires_at && request.expires_at < Date.now()/1000) continue;
    jobs.push({request, response});
    if (jobs.length >= limit) break;
  }
  return await Promise.all(jobs.map(async ({request: q, response}) => {
    let result;
    try {
      const url = new URL(q.url);
      if (url.origin !== origins[q.service] || !url.pathname.startsWith('/api/') ||
          (q.service === 'asana' && q.method !== 'GET')) throw new Error('Request outside configured API scope');
      if(q.service==='pms' && q.method!=='GET' &&
         !((q.method==='POST' && /^\/api\/projects\/\d+\/periods$/.test(url.pathname)) ||
           (q.method==='PUT' && /^\/api\/projects\/\d+\/periods\/\d+$/.test(url.pathname))))
        throw new Error('Only project KPI period writes are supported');
      for (const [key, value] of Object.entries(q.params || {})) url.searchParams.set(key, String(value));
      const job = {path: url.pathname + url.search, method: q.method, body: q.body, service: q.service,
        headers:q.headers?.['Last-Modified'] ? {'Last-Modified':q.headers['Last-Modified']} : {}};
      const expression = `(async(q)=>{
        const headers={'Accept':'application/json','Content-Type':'application/json',...q.headers};
        if(q.service==='pms'){
          let token=localStorage.getItem('token');try{token=JSON.parse(token)}catch{}
          if(token) headers.Authorization='Bearer '+token;
        }
        const r=await fetch(q.path,{method:q.method,credentials:'include',headers,
          ...(q.body===null?{}:{body:JSON.stringify(q.body)})});
        if(!r.ok)return {error:'API returned '+r.status+' for '+q.path.split('?')[0]};
        const text=await r.text();return {data:text?JSON.parse(text):{}};
      })(${JSON.stringify(job)})`;
      const remote = await clients[q.service].send('Runtime.evaluate', {
        expression, awaitPromise: true, returnByValue: true
      }, {timeoutMs:15000});
      if (remote.exceptionDetails || !remote.result?.value) throw new Error('Browser API request did not return data');
      result = remote.result.value;
    } catch (error) { result = {error: String(error.message || error)}; }
    await fs.writeFile(response + '.tmp', JSON.stringify(result), {mode: 0o600});
    await fs.rename(response + '.tmp', response);
    return {service:q.service, method:q.method, ok:!result.error, error:result.error};
  }));
}

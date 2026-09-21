/* Map the pipeline's small Google API surface to a host's connected Drive tools.
 * The caller supplies tools and a file download callback; no account data is embedded.
 */
function unwrap(result) {
  if (result.isError) throw new Error(JSON.stringify(result.structuredContent || result.content));
  if (result.structuredContent) return result.structuredContent;
  const text = result.content?.find(x => x.type === 'text')?.text;
  try { return JSON.parse(text); } catch { throw new Error('Connector returned no structured data'); }
}
function driveMeta(x) {
  return {id:x.id || x.fileId || x.file_id, name:x.name || x.title,
    mimeType:x.mimeType || x.mime_type, modifiedTime:x.modifiedTime || x.modified_time,
    parents:x.parents || x.parent_ids, webViewLink:x.webViewLink || x.url};
}
function column(n) { let s='';for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s; }

export async function respond(q, tools, download) {
  if(q.expires_at && q.expires_at < Date.now()/1000)throw new Error('Host request expired; run again');
  const parsed = /^(https:\/\/[^/]+)(\/[^?#]*)/.exec(q.url);
  if(!parsed)throw new Error('Invalid Google API URL');
  const u = {origin:parsed[1],pathname:parsed[2]}, p = q.params || {}, b = q.body || {};
  const call = async (name, args) => unwrap(await tools['mcp__codex_apps__google_drive_'+name](args));
  if (u.origin === 'https://www.googleapis.com' && u.pathname.startsWith('/drive/v3/files')) {
    const parts=u.pathname.split('/').filter(Boolean), id=parts[3];
    if(q.raw) {
      const result=await call('fetch',{url:'https://drive.google.com/file/d/'+id+'/view',
        download_raw_file:true,include_base64:false,...(p.mimeType?{raw_export_mime_type:p.mimeType}:{})});
      const ref=result.file_uri || result.structuredContent?.file_uri;
      if(!ref?.download_url)throw new Error('Drive download did not return a complete file');
      return {file:await download(ref.download_url,q.id)};
    }
    if(q.method==='GET' && id)return {data:driveMeta(await call('get_file_metadata',{fileId:id,fields:p.fields}))};
    if(q.method==='GET') {
      const result=await call('search',{special_filter_query_str:p.q,topn:5,best_effort_fetch:false});
      const files=result.files || result.results || result.items;
      if(!Array.isArray(files))throw new Error('Unexpected Drive search shape');
      return {data:{files:files.map(driveMeta)}};
    }
    if(q.method==='POST' && parts[4]==='copy')return {data:driveMeta(await call('copy_file',{
      url:'https://drive.google.com/file/d/'+id+'/view',new_title:b.name,parent_folder:b.parents?.[0]}))};
    if(q.method==='POST' && !id){
      let file=driveMeta(await call('create_file',{mime_type:b.mimeType,title:b.name}));
      if(b.parents?.[0])file=driveMeta(await call('update_file',{fileId:file.id,addParents:b.parents[0]}));
      return {data:file};
    }
    throw new Error('Unsupported Drive operation');
  }
  if(u.origin==='https://sheets.googleapis.com' && u.pathname.startsWith('/v4/spreadsheets/')) {
    const suffix=u.pathname.slice('/v4/spreadsheets/'.length), id=suffix.split(/[/:]/)[0];
    if(q.method==='POST' && suffix.endsWith(':batchUpdate')) {
      await call('batch_update_spreadsheet',{spreadsheet_id:id,requests:b.requests});
      return {data:{}};
    }
    const meta=await call('get_spreadsheet_metadata',{spreadsheet_id:id,include_conditional_format_rules:true});
    if(suffix.endsWith('/values:batchGet')) {
      const ranges=p.ranges.map(name=>{
        const title=name.replace(/^'|'$/g,'').replace(/''/g,"'");
        const sheet=meta.sheets.find(s=>s.properties.title===title);
        if(!sheet)throw new Error('Review sheet tab is missing: '+title);
        const grid=sheet.properties.gridProperties;
        return name+'!A1:'+column(grid.columnCount)+grid.rowCount;
      });
      const data=await call('get_spreadsheet_cells',{spreadsheet_id:id,ranges,cell_fields:'formattedValue'});
      return {data:{valueRanges:p.ranges.map(name=>{
        const title=name.replace(/^'|'$/g,'').replace(/''/g,"'");
        const sheet=data.sheets.find(s=>s.properties.title===title);
        if(!sheet)throw new Error('Incomplete review sheet read: '+title);
        const rows=sheet.data?.[0]?.rowData || [];
        return {range:name,values:rows.map(r=>(r.values||[]).map(c=>c.formattedValue??''))};
      })}};
    }
    return {data:meta};
  }
  throw new Error('Request outside Google API scope');
}

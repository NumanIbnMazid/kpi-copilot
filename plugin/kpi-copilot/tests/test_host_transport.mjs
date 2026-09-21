// Synthetic fixtures only: no live account or browser is contacted.
import assert from 'node:assert/strict';
import {respond} from '../scripts/google_transport.mjs';
import {drain} from '../scripts/browser_transport.mjs';

const wrapped = data => ({structuredContent:data});
let calls=0;
const tools={mcp__codex_apps__google_drive_search:async()=>{
  calls++; return wrapped({results:[{id:'example',title:'Workbook',mime_type:'sheet'}]});
}};
const request={id:'one',method:'GET',url:'https://www.googleapis.com/drive/v3/files',params:{q:'fictional'}};
assert.equal((await respond(request,tools)).data.files[0].id,'example');
await assert.rejects(()=>respond({...request,expires_at:1},tools),/expired/);
assert.equal(calls,1);
tools.mcp__codex_apps__google_drive_search=async()=>wrapped({unexpected:[]});
await assert.rejects(()=>respond(request,tools),/search shape/);
await assert.rejects(()=>respond({...request,url:'https://unrelated.example/api/data'},tools),/scope/);

const pending={id:'one',service:'pms',method:'DELETE',url:'https://pms.example/api/projects/1/periods/2',expires_at:Date.now()/1000+60};
const files=new Map([['/private/one.request.json',JSON.stringify(pending)]]);
let browserCalls=0;
const fs={readdir:async()=>['one.request.json'],access:async p=>{if(!files.has(p))throw Error('absent')},
  readFile:async p=>files.get(p),writeFile:async(p,data)=>files.set(p,data),
  rename:async(a,b)=>{files.set(b,files.get(a));files.delete(a)}};
const opts={directory:'/private',fs,origins:{pms:'https://pms.example'},
  clients:{pms:{send:async()=>{browserCalls++;return {result:{value:{data:{ok:true}}}}}}}};
assert.equal((await drain(opts))[0].ok,false);
assert.equal(browserCalls,0);
files.delete('/private/one.response.json');
pending.method='PUT';pending.expires_at=1;
files.set('/private/one.request.json',JSON.stringify(pending));
assert.deepEqual(await drain(opts),[]);
assert.equal(browserCalls,0);
console.log('Connected-host driver guards passed');

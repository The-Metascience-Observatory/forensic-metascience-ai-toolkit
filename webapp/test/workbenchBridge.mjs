// The bridge's framing, restart and cancellation, against a scripted fake
// service: no Python, no database, no server. Run with
// `node --experimental-strip-types test/workbenchBridge.mjs`.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { PassThrough } from 'node:stream';

const dir=fs.mkdtempSync(path.join(os.tmpdir(),'workbench-bridge-'));
const fake=path.join(dir,'python');
fs.writeFileSync(fake,`#!${process.execPath}
const readline=require('node:readline');const cancels=[];
readline.createInterface({input:process.stdin}).on('line',line=>{
  const r=JSON.parse(line);
  if(r.method==='cancel'){cancels.push(r.params.id);return;}
  if(r.method==='hang')return;
  if(r.method==='cancels'){process.stdout.write(JSON.stringify({id:r.id,result:cancels})+'\\n');return;}
  if(r.method==='echo'){
    // Several chunks long, multibyte characters at every offset parity.
    const text='é€😀x'.repeat(40000);
    const body=Buffer.from(JSON.stringify({id:r.id,result:text})+'\\n');
    // Write in odd-sized slices so chunk boundaries fall inside characters.
    for(let at=0;at<body.length;at+=65537)process.stdout.write(body.subarray(at,at+65537));
  }
});
`,{mode:0o755});
process.env.METASCIENCE_PYTHON=fake;
const { frameLines, workbench, restartWorkbench } = await import('../lib/workbench.ts');

// 1. A character split across two chunks survives decoding.
{
  const stream=new PassThrough(),lines=[];
  frameLines(stream,line=>lines.push(line),()=>assert.fail('overflow'));
  const bytes=Buffer.from('{"a":"é😀"}\n{"b":1}\n','utf8');
  stream.write(bytes.subarray(0,7));stream.write(bytes.subarray(7,9));stream.end(bytes.subarray(9));
  await new Promise(r=>stream.on('end',r));
  assert.deepEqual(lines,['{"a":"é😀"}','{"b":1}']);
  assert.ok(!lines.join('').includes('�'));
}
// 2. A multi-chunk response from a real child process arrives intact.
{
  const text=await workbench('echo');
  assert.equal(text,'é€😀x'.repeat(40000));
}
// 3. An abandoned request is withdrawn from the service, by id.
{
  const controller=new AbortController();
  const hung=workbench('hang',{n:1},{signal:controller.signal});
  controller.abort();
  await assert.rejects(hung,/cancelled/);
  // A second waiter on the same read keeps it alive until it, too, leaves.
  const a=new AbortController();
  const first=workbench('status',{n:2},{signal:a.signal}),second=workbench('status',{n:2});
  a.abort();await assert.rejects(first,/cancelled/);
  const cancels=await workbench('cancels');
  assert.equal(cancels.length,1,'only the request nobody waits for is cancelled');
  // 4. A restart rejects what the old process still owed, immediately.
  const started=Date.now();
  restartWorkbench();
  await assert.rejects(second,/restarted/);
  assert.ok(Date.now()-started<1000);
}
fs.rmSync(dir,{recursive:true,force:true});
console.log('workbench bridge: split UTF-8, multi-chunk framing, cancellation and restart passed');
process.exit(0);

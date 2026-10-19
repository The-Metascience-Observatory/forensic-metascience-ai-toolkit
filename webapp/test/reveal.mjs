import {rejectCrossOrigin} from '../lib/mutation.ts';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
import {linuxRevealArgv, revealLocation, runRevealCommand} from '../lib/reveal.ts';

const file = '/papers/quoted "name" #1/paper.pdf';
const args = linuxRevealArgv('/papers', file);
assert.equal(args[args.indexOf('--method') + 1], 'org.freedesktop.FileManager1.ShowItems');
assert.deepEqual(JSON.parse(args.at(-2)), ['file:///papers/quoted%20%22name%22%20%231/paper.pdf']);
assert.equal(linuxRevealArgv('/papers', null).includes('org.freedesktop.FileManager1.ShowFolders'), true);
let calls=[];
assert.deepEqual(await revealLocation('linux', '/papers', file, async argv=>{calls.push(argv);}), {selected:true});
assert.deepEqual(calls,[args]);
calls=[];
assert.deepEqual(await revealLocation('linux', '/papers', file, async argv=>{
  calls.push(argv); if(argv[0]==='gdbus') throw Error('no desktop service');
}), {selected:false});
assert.deepEqual(calls[1], ['xdg-open','/papers']);
await assert.rejects(revealLocation('linux','/papers',file,async()=>{throw Error('display unavailable');}), /Could not open.*display unavailable/s);
await assert.rejects(runRevealCommand(['nonexistent-reveal-test-executable']), /ENOENT/);
await assert.rejects(runRevealCommand([process.execPath,'-e','process.stderr.write("launcher failed");process.exit(3)']), /launcher failed/);

// Exercise the HTTP handler with a virtual archive reference. It must resolve
// through the same workbench authority as /api/media before invoking any GUI.
const source=readFileSync(new URL('../app/api/reveal/route.ts',import.meta.url),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
const endpoint={}; let resolved,launched; let resolverError,launcherError;
vm.runInNewContext(code,{exports:endpoint,process:{platform:'linux'},URL,require:name=>({
  'next/server':{NextResponse:Response},
  '@/lib/mutation':{rejectCrossOrigin},
  '@/lib/err':{errMsg:e=>e.message},
  '@/lib/workbench':{workbench:async(method,params)=>{
    resolved={method,params}; if(resolverError)throw resolverError;
    return {directory:'/registered/paper',file:'/registered/paper/paper.pdf'};
  }},
  '@/lib/reveal':{revealLocation:async(...argv)=>{
    launched=argv;if(launcherError)throw launcherError;return {selected:true};
  }},
}[name])});
const body={project:'project',dir:'paper',f:'__runs/run-id/artifact-id'};
const request=(origin='http://localhost:3100',data=body)=>new Request('http://localhost:3100/api/reveal',{
  method:'POST',headers:{origin,'content-type':'application/json'},body:JSON.stringify(data)});
const response=await endpoint.POST(request());
assert.equal(response.status,200);
assert.equal((await response.json()).opened,'/registered/paper/paper.pdf');
assert.equal(JSON.stringify(resolved.params),JSON.stringify(body));
assert.equal(resolved.method,'reveal_target');
assert.equal(JSON.stringify(launched),JSON.stringify(['linux','/registered/paper','/registered/paper/paper.pdf']));
launched=null; resolverError=Error('Archived source unavailable');
assert.equal((await endpoint.POST(request())).status,400);
assert.equal(launched,null);
resolverError=null;launcherError=Error('File manager launch failed');
assert.equal((await (await endpoint.POST(request())).json()).error,'File manager launch failed');
launched=null;
assert.equal((await endpoint.POST(request('https://other.example'))).status,403);
assert.equal(launched,null);
assert.equal((await endpoint.POST(request('http://localhost:3100',null))).status,400);
console.log('reveal: archive resolver, Caja desktop protocol, fallback and visible launch failures passed');

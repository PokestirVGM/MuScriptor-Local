// Exercise real TypeScript methods with controlled browser/network boundaries.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('../upstream/web/node_modules/typescript');
const root = path.resolve(__dirname, '../upstream/web/src');
function deferred() { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; }
function load(file, imports = {}, globals = {}) {
  const exports = {};
  const source = ts.transpileModule(fs.readFileSync(path.join(root,file),'utf8'), {
    compilerOptions: {target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX},
  }).outputText;
  vm.runInNewContext(source, {exports, require(name) {
    if (!(name in imports)) throw Error(`Unexpected import ${name}`);
    return imports[name];
  }, crypto, performance, Blob, File, URL, AbortController, atob, btoa, setTimeout, ...globals}, {filename:file});
  return exports;
}
const tick = () => new Promise(resolve => setImmediate(resolve));
function audioFixture() {
  const {AudioEngine} = load('audio.ts', {'tone':{},'spessasynth_lib':{},'spessasynth_lib/dist/spessasynth_processor.min.js?url':{}});
  const audio = Object.create(AudioEngine.prototype);
  Object.assign(audio, {wavGeneration:0,wavBuffer:null,channels:new Map(),mutedInstruments:new Set(),
    stop(){},stopWavSource(){},applyMix(){}});
  return audio;
}
test('newest audio wins even when the older decode finishes last', async () => {
  const audio=audioFixture(); const first=deferred(); const second=deferred();
  audio.ctx={decodeAudioData: data => data === 'first' ? first.promise : second.promise};
  const old=audio.loadWav({arrayBuffer:async()=> 'first'}); await tick();
  const next=audio.loadWav({arrayBuffer:async()=> 'second'}); await tick();
  second.resolve({duration:12}); await next; first.resolve({duration:99}); await old;
  assert.equal(audio.duration,12);
});
test('reset prevents a pending decode from restoring old audio', async () => {
  const audio=audioFixture(); const decode=deferred(); audio.ctx={decodeAudioData:()=>decode.promise};
  const pending=audio.loadWav({arrayBuffer:async()=>new ArrayBuffer(0)}); await tick();
  audio.reset(); decode.resolve({duration:99}); await pending;
  assert.equal(audio.duration,0);
});
test('a stale decode failure cannot clear newer audio', async () => {
  const audio=audioFixture(); const old=deferred();
  audio.ctx={decodeAudioData: data => data === 'old' ? old.promise : Promise.resolve({duration:7})};
  const pending=audio.loadWav({arrayBuffer:async()=> 'old'}); await tick();
  await audio.loadWav({arrayBuffer:async()=> 'new'}); old.reject(Error('bad audio')); await pending;
  assert.equal(audio.duration,7);
});
function hookFixture({fetch,stream=async function*(){},audioLoad=async()=>{}}) {
  const applied=[], states=[], errors=[], files=[];
  const sse=load('sse.ts');
  const {useTranscription}=load('hooks/useTranscription.ts', {
    'react':{useRef: value=>({current:value}),useState: value=>[value,()=>{}]},
    '../sse':{...sse,streamTranscribeWithRetry:stream},
    '../sessionStorage':{encodeAudio:async()=>'',saveRecovery:async()=>{}},
    '../analytics':{track(){}}, '../pianoroll':{},
  }, {fetch,requestAnimationFrame: callback=>callback()});
  const noop=()=>{};
  const hook=useTranscription({audio:{reset:noop,loadWav:audioLoad,unlock:async()=>{},replaceNotes:noop,scheduleStop:noop},
    rollRef:{current:null},getConditioning:()=>[],getTiming:()=>({mode:'manual',bpm:120}),
    onRhythm:r=>applied.push(r),onRecovery:noop,onSessionTiming:noop,
    progress:{reset:noop,onAnchor:noop},onError:e=>errors.push(e),onAccepted:noop,onBusy:noop,
    setAppState:s=>states.push(s),setInstruments:noop,setResult:noop,setCurrentFile:f=>files.push(f),setUserScrolled:noop});
  return {hook,applied,states,errors,files};
}
function response(name) { return {ok:true,json:async()=>({name,session:name,data:btoa('midi'),notes:[],timing:{},duration:10})}; }
test('late session import does not replace a more recently opened session', async () => {
  const old=deferred();
  const f=hookFixture({fetch:async (url, options) => url === '/session/import'
    ? JSON.parse(options.body).name === 'old' ? old.promise : response('new')
    : {ok:true,json:async()=>({})}});
  const pending=f.hook.openSession({name:'old'});
  await f.hook.openSession({name:'new'}); old.resolve(response('old')); await pending;
  assert.equal(f.applied.length,1); assert.equal(f.applied[0].session,'new');
});
test('leaving while session audio decodes does not restore a closed session', async () => {
  const decode=deferred();
  const f=hookFixture({fetch:async()=>response('audio'),audioLoad:()=>decode.promise});
  const pending=f.hook.openSession({name:'audio',audio:btoa('wav')}); await tick();
  f.hook.abort(); decode.resolve(); await pending;
  assert.equal(f.applied.length,0); assert.ok(!f.states.includes('done'));
});
test('an incomplete stream reports a failure instead of claiming completion', async () => {
  const f=hookFixture({fetch:async()=>response('unused')});
  await f.hook.transcribe(new File(['audio'],'song.wav'));
  assert.ok(!f.states.includes('done')); assert.equal(f.states.at(-1),'error');
  assert.match(f.errors[0],/before the MIDI was ready/);
});
test('Cancel sends only its active run ID and ignores late stream data', async () => {
  const gate=deferred(); let runId; const requests=[];
  const f=hookFixture({fetch:async(url,options)=>{requests.push({url,options});return response('unused');},
    stream:async function*(_url,_file,options) {runId=options.extra.run_id; await gate.promise; yield {type:'transcription_complete',data:btoa('midi'),notes:[]};}});
  const pending=f.hook.transcribe(new File(['audio'],'song.wav')); await tick();
  f.hook.abort(); gate.resolve(); await pending;
  assert.equal(requests.length,1); assert.equal(requests[0].url,'/transcribe/cancel');
  assert.equal(JSON.parse(requests[0].options.body).run_id,runId);
  assert.equal(f.applied.length,0); assert.ok(!f.states.includes('done'));
});
test('audio-less session stays audible after original-only and stereo playback', () => {
  const audio=audioFixture(); delete audio.applyMix;
  const values={}; const parameter=name=>({setTargetAtTime(value){values[name]=value;}});
  Object.assign(audio,{ctx:{currentTime:0},wavGain:{gain:parameter('original')},midiGain:{gain:parameter('midi')},wavPanner:{pan:parameter('originalPan')},midiPanner:{pan:parameter('midiPan')}});
  for (const stereo of [false,true]) {
    audio.mix=0; audio.stereo=stereo; audio.applyMix();
    assert.equal(values.midi,1); assert.equal(values.midiPan,0); assert.equal(audio.hasOriginal,false);
  }
  audio.wavBuffer={duration:12,numberOfChannels:2}; audio.stereo=false; audio.applyMix();
  assert.equal(values.original,1); assert.equal(values.midi,0); assert.equal(audio.hasOriginal,true);
});

function outputFixture() {
  const cells=[]; let cursor=0; let effects=[]; let props; const downloads=[], alerts=[], requests=[];
  const react={
    useState(initial){const i=cursor++; if(!cells[i]) cells[i]={value:initial}; return [cells[i].value,v=>{cells[i].value=typeof v==='function'?v(cells[i].value):v;}];},
    useRef(initial){const i=cursor++; return cells[i]??=( {current:initial} );},
    useEffect(fn,deps){const i=cursor++; const prior=cells[i]; if(!prior || deps.some((v,j)=>v!==prior.deps[j])) {cells[i]={deps}; effects.push(()=>{prior?.cleanup?.(); cells[i].cleanup=fn();});}},
  };
  const jsx=(type,props)=>({type,props});
  const {OutputBar}=load('components/OutputBar.tsx', {
    react, 'react/jsx-runtime':{jsx,jsxs:jsx,Fragment:'fragment'}, clsx:()=>'',
    fflate:{unzipSync:()=>({'score.pdf':new Uint8Array([1])})}, './Button':{Button:'button'},
    './SheetsDialog':{SheetsDialog:'sheets-dialog'}, './icons':{IconChevron:'icon',IconDownload:'icon'}, '../analytics':{track(){}},
  }, {FormData, setTimeout:()=>0, document:{addEventListener(){},removeEventListener(){},createElement(){const link={click(){downloads.push(link);}};return link;}},
    alert:m=>alerts.push(m), fetch:async(url,options)=> {
      if(url==='/capabilities') return {ok:true,json:async()=>({fluidsynth:true,sheets:true})};
      const reply=deferred(); requests.push({url,options,reply}); return reply.promise;
    }});
  const render=(next=props)=>{props=next;cursor=0;const tree=OutputBar(props);const pending=effects;effects=[];pending.forEach(f=>f());return tree;};
  const nodes=tree=>tree==null||typeof tree!=='object'?[]:Array.isArray(tree)?tree.flatMap(nodes):[tree,...nodes(tree.props?.children)];
  const label=node=>nodes(node).flatMap(n=>Array.isArray(n.props?.children)?n.props.children:[n.props?.children]).filter(c=>typeof c==='string').join(' ');
  const click=async(name)=>{let tree=render();let node=nodes(tree).find(n=>n.type==='button'&&label(n).trim()===name);assert.ok(node,`Missing button ${name}`);assert.ok(!node.props.disabled,`${name} is disabled`);return node.props.onClick({currentTarget:{blur(){}}});};
  const result=name=>({filename:name+'.mid',url:'blob:'+name,midi:new Blob(['selected']),performanceMidi:new Blob(['original']),quantizedMidi:null});
  render({transcribing:false,result:result('first'),currentFile:null,progressFillRef:{current:null},progressLabelRef:{current:null},onTranscribeAnother(){}});
  return {render,nodes,click,requests,downloads,alerts,result,get props(){return props;}};
}
test('synthesis export works without source audio and uses the selected MIDI',async()=>{
  const f=outputFixture(); await tick(); await f.click('Download'); const pending=f.click('WAV - transcription only'); await tick();
  assert.equal(f.requests.length,1); assert.equal(f.requests[0].options.body.get('mode'),'synth');
  assert.equal(await f.requests[0].options.body.get('midi').text(),'selected');
  f.requests[0].reply.resolve({ok:true,blob:async()=>new Blob(['wav'])}); await pending; await tick();
  assert.equal(f.downloads.length,1); assert.equal(f.downloads[0].download,'first_transcription.wav');
});
test('old sheet render cannot populate a newer result',async()=>{
  const f=outputFixture();await tick();await f.click('Download');const pending=f.click('Sheet music');await tick();
  f.render({...f.props,result:f.result('new')});
  f.requests[0].reply.resolve({ok:true,blob:async()=>new Blob(['zip'])});await pending; await tick();
  assert.equal(f.alerts.length,0, f.alerts.join(' '));
  assert.ok(!f.nodes(f.render()).some(n=>n.type==='sheets-dialog'));
});

function recoveryFixture(initial, fetch) {
  let stored=initial;
  const db={close(){}, transaction(){
    const tx={objectStore(){return {
      get(){const request={};queueMicrotask(()=>{request.result=stored;request.onsuccess();queueMicrotask(()=>tx.oncomplete?.());});return request;},
      put(value){stored=value;queueMicrotask(()=>tx.oncomplete?.());},
      delete(){stored=undefined;queueMicrotask(()=>tx.oncomplete?.());},
      count(){const request={};queueMicrotask(()=>{request.result=stored?1:0;request.onsuccess();});return request;},
    };}};return tx;
  }};
  const indexedDB={open(){const request={result:db};queueMicrotask(()=>request.onsuccess());return request;}};
  return {...load('sessionStorage.ts',{}, {indexedDB,fetch}),get stored(){return stored;}};
}
test('recovery uses a newer browser fallback instead of an older disk copy',async()=>{
  const local={name:'new browser',recovery_saved_at:200};const disk={name:'old disk',recovery_saved_at:100};
  const f=recoveryFixture(local,async()=>({ok:true,json:async()=>disk}));
  assert.equal((await f.readRecovery()).name,'new browser');
});
test('recovery uses a newer desktop save instead of an older browser fallback',async()=>{
  const f=recoveryFixture({name:'old browser',recovery_saved_at:100},async()=>({ok:true,json:async()=>({name:'new disk',recovery_saved_at:200})}));
  assert.equal((await f.readRecovery()).name,'new disk');
});
test('successful disk recovery save clears an obsolete browser fallback',async()=>{
  const f=recoveryFixture({name:'obsolete'},async()=>({ok:true}));
  await f.saveRecovery({name:'new'});assert.equal(f.stored,undefined);
});
test('disconnected recovery fallback records freshness and stays readable',async()=>{
  const f=recoveryFixture(undefined,async()=>{throw Error('offline');});
  await f.saveRecovery({name:'offline'});assert.ok(f.stored.recovery_saved_at>0);
  assert.equal((await f.readRecovery()).name,'offline');
});
test('an older disk save cannot erase a more recent browser fallback',async()=>{
  const f=recoveryFixture({name:'newer fallback',recovery_saved_at:Date.now()+60000},async()=>({ok:true}));
  await f.saveRecovery({name:'older'});assert.equal(f.stored.name,'newer fallback');
});
test('late WAV export does not download a previous result',async()=>{
  const f=outputFixture();await tick();await f.click('Download');await f.click('WAV - transcription only');await tick();
  f.render({...f.props,result:f.result('new')});
  assert.equal(f.requests[0].options.signal.aborted,true);
  f.requests[0].reply.resolve({ok:true,blob:async()=>new Blob(['wav'])});await tick();
  assert.equal(f.downloads.length,0);assert.equal(f.alerts.length,0);
});
test('comparison WAV retains original performance and includes the source audio',async()=>{
  const f=outputFixture();f.render({...f.props,currentFile:new File(['source'],'song.wav')});await tick();
  await f.click('Download');await f.click('WAV - stereo with original');await tick();
  const form=f.requests[0].options.body;assert.equal(await form.get('midi').text(),'original');assert.equal(await form.get('audio').text(),'source');
  f.requests[0].reply.resolve({ok:true,blob:async()=>new Blob(['wav'])});await tick();
  assert.equal(f.downloads.length,1);
});
test('a current sheet render still opens its download dialog',async()=>{
  const f=outputFixture();await tick();await f.click('Download');await f.click('Sheet music');await tick();
  f.requests[0].reply.resolve({ok:true,blob:async()=>new Blob(['zip'])});await tick();
  assert.ok(f.nodes(f.render()).some(n=>n.type==='sheets-dialog'));
});

// Run the editor script against a stub DOM and report any load-time error.
const fs = require('fs'), vm = require('vm');
const html = fs.readFileSync(process.argv[2], 'utf8');
const src = html.split('<script>')[1].split('</script>')[0];
const ids = new Set([...html.matchAll(/id="([\w-]+)"/g)].map(m => m[1]));
const make = id => new Proxy({id, style:{}, dataset:{},
  classList:{add(){},remove(){},toggle(){},contains(){return false}},
  append(){}, prepend(){}, remove(){}, querySelector(){return make('x')},
  querySelectorAll(){return []}, files:[], addEventListener(){}, focus(){},
  select(){}, click(){}, scrollIntoView(){}, showModal(){}, close(){},
  insertAdjacentHTML(){}, getBoundingClientRect(){return {left:0,top:0,width:800,height:1000}}},
  {get(t,k){return k in t ? t[k] : undefined}, set(t,k,v){t[k]=v;return true}});
const missing = [];
const doc = {
  querySelector(sel){ const id = sel.replace('#','');
    if (sel.startsWith('#') && !ids.has(id)) { missing.push(id); return null; }
    return make(id); },
  querySelectorAll(){ return []; }, createElement(){ return make('new'); },
  getElementById(){ return make('x'); }, addEventListener(){}, body: make('body'),
};
const ctx = { document: doc, console, fetch: () => new Promise(()=>{}),
  localStorage: {getItem(){return null}, setItem(){}}, alert(){}, confirm(){return true},
  prompt(){return null}, setTimeout(){}, clearTimeout(){}, addEventListener(){},
  Date, Math, JSON, Object, Array, Number, String, Boolean, parseInt, parseFloat,
  isNaN, encodeURIComponent, FileReader: function(){ return make('fr'); },
  navigator: {clipboard:{writeText(){ return Promise.resolve(); }}},
};
for (const d of ['dlgNew','dlgVersions','dlgScreens','dlgRewrite','dlgQA','dlgAdmin','dlgCredits'])
  ctx[d] = make(d);
ctx.window = ctx;
try {
  vm.createContext(ctx);
  vm.runInContext(src, ctx, {timeout: 5000});
  console.log('OK: the script ran to the end, so every handler is bound');
} catch (e) {
  console.log('THREW AT LOAD:', e.message);
  const line = (e.stack.match(/evalmachine[^\n]*:(\d+)/) || [])[1];
  if (line) console.log('  line ' + line + ': ' + src.split('\n')[line-1].trim().slice(0,110));
  process.exitCode = 1;
}
console.log('ids referenced but absent from the markup:',
            missing.length ? [...new Set(missing)] : 'none');

const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');

function environment() {
  const listeners={}, windowListeners={}, calls=[], moves=[], states=[];
  let path='/', revision='same';
  const location={origin:'https://store.test',href:'https://store.test/',assign(href){moves.push(['assign',href]);},reload(){moves.push(['reload']);}};
  Object.defineProperties(location,{pathname:{get(){return new URL(this.href).pathname;}},search:{get(){return new URL(this.href).search;}}});
  const classList={toggle(){},add(){}};
  const heading={setAttribute(){},focus(){}};
  const main={setAttribute(){},removeAttribute(){}};
  const themeSpan={textContent:''};
  const theme={setAttribute(){},querySelector(){return themeSpan;}};
  const region={id:'navigation-status',classList,setAttribute(){},textContent:''};
  const body={dataset:{defaultMode:'light'},attributes:[],children:[],removeAttribute(){},setAttribute(){},append(){},replaceChildren(...nodes){this.children=nodes;path=nodes[0].path;}};
  const head={querySelectorAll(){return [];},append(){}};
  const document={body,head,documentElement:{dataset:{}},hidden:false,title:'Home',addEventListener(name,fn){listeners[name]=fn;},dispatchEvent(){},getElementById(id){return id==='navigation-status'?region:null;},querySelector(q){
    if(q==='.mode-toggle')return theme;if(q==='main')return main;if(q==='main h1')return heading;
    if(q==='meta[name="rincon-revision"]')return {content:revision};return null;
  },createElement(){return region;},importNode(n){return n;}};
  const history={state:null,scrollRestoration:'auto',replaceState(state,_,href){this.state=state;states.push(state);location.href=new URL(href,location.href).href;},pushState(state,_,href){this.state=state;states.push(state);location.href=new URL(href,location.href).href;}};
  class FormData {
    constructor(form){this.data=Object.entries(form.fields||{});}
    append(key,value){this.data.push([key,value]);}
    [Symbol.iterator](){return this.data[Symbol.iterator]();}
  }
  class Form {
    constructor(action,method='post'){this.action=action;this.method=method;this.fields={csrf_token:'test-token'};this.attrs={};this.target='';this.buttons=[];}
    hasAttribute(key){return key in this.attrs;}
    setAttribute(key,value){this.attrs[key]=value;}
    matches(){return false;}
    querySelectorAll(){return this.buttons;}
  }
  class DOMParser {
    parseFromString(html){const data=JSON.parse(html);return {title:data.title||data.path,head:{querySelectorAll(){return [];}},body:{attributes:[],childNodes:[{path:data.path,nodeName:'MAIN'}]},querySelectorAll(){return [];},querySelector(q){
      if(q==='meta[name="rincon-app"]')return {};
      if(q==='main')return {};
      if(q==='meta[name="rincon-revision"]')return {content:data.revision||'same'};
      return null;
    }};}
  }
  let responder=async (href,options)=>({url:options.method==='POST'?'https://store.test/carrito':href,status:200,headers:{get(){return 'text/html';}},text:async()=>JSON.stringify({path:options.method==='POST'?'/carrito':new URL(href).pathname})});
  const context={document,location,history,HTMLFormElement:Form,FormData,DOMParser,URL,URLSearchParams,AbortController,Event,Intl,setTimeout,clearTimeout,scrollX:0,scrollY:0,scrollTo(value){moves.push(['scroll',value]);},matchMedia(){return {matches:false,addEventListener(){}};},localStorage:{getItem(){return null;},setItem(){}},confirm(){return true;}};
  context.window=context;
  context.addEventListener=(name,fn)=>windowListeners[name]=fn;
  context.fetch=async (href,options)=>{calls.push({href,options});return responder(href,options);};
  vm.runInNewContext(fs.readFileSync('app/static/experience.js','utf8'),context);
  const tick=async()=>{for(let i=0;i<8;i++)await new Promise(resolve=>setImmediate(resolve));};
  const link=(href,extra={})=>({href,target:'',hasAttribute(){return false;},...extra});
  function click(anchor){let prevented=false;listeners.click({target:{closest(selector){return selector==='.mode-toggle'?null:anchor;}},button:0,preventDefault(){prevented=true;}});return prevented;}
  function submit(form,submitter){let prevented=false;listeners.submit({target:form,submitter,preventDefault(){prevented=true;}});return prevented;}
  return {context,Form,calls,moves,states,document,location,history,windowListeners,themeSpan,click,link,submit,tick,get path(){return path;},set responder(value){responder=value;}};
}

test('links use one document, update history and support back',async()=>{
  const e=environment(), original=e.document;
  assert.equal(e.click(e.link('https://store.test/catalogo')),true);await e.tick();
  assert.equal(e.document,original);assert.equal(e.path,'/catalogo');assert.equal(e.location.pathname,'/catalogo');
  assert.equal(e.moves.some(x=>x[0]==='assign'),false);
  e.location.href='https://store.test/';e.windowListeners.popstate({state:{rincon:true,x:0,y:125}});await e.tick();
  assert.equal(e.path,'/');assert.equal(e.moves.at(-1)[1].top,125);
  assert(e.states.every(state=>!('html' in state))); // No private page cache in history.
});

test('POST uses the form action and pressed button, not submitter default URL',async()=>{
  const e=environment(), form=new e.Form('https://store.test/carrito/agregar/1');
  const button={name:'intent',value:'buy_now',formAction:'https://store.test/producto/1',hasAttribute(){return false;},getAttribute(){return null;}};
  assert.equal(e.submit(form,button),true);await e.tick();
  assert.equal(e.calls[0].href,'https://store.test/carrito/agregar/1');
  assert.deepEqual([...e.calls[0].options.body],[['csrf_token','test-token'],['intent','buy_now']]);
  assert.equal(e.path,'/carrito');assert.equal(e.location.pathname,'/carrito');
});

test('GET filters serialize correctly and assets are not reloaded',async()=>{
  const e=environment(), form=new e.Form('https://store.test/catalogo','get');form.fields={q:'colores y juegos',tipo:'digital'};
  e.submit(form);await e.tick();assert.match(e.calls[0].href,/q=colores\+y\+juegos/);assert.match(e.calls[0].href,/tipo=digital/);
  assert.equal(e.calls.length,1);
});

test('external checkout and downloads retain native navigation',async()=>{
  const e=environment();
  assert.equal(e.submit(new e.Form('https://store.test/pedido/signed/pagar')),false);
  assert.equal(e.click(e.link('https://mercadopago.com/checkout')),false);
  assert.equal(e.click(e.link('https://store.test/pedido/signed/descarga/1')),false);
  assert.equal(e.click(e.link('https://store.test/catalogo',{target:'_blank'})),false);
  await e.tick();assert.equal(e.calls.length,0);
});

test('uncertain POST is not retried or submitted twice',async()=>{
  const e=environment(), form=new e.Form('https://store.test/pedido/nuevo');
  let reject;e.responder=()=>new Promise((_,r)=>reject=r);
  e.submit(form);e.submit(form);assert.equal(e.calls.length,1);
  reject(new Error('Network lost'));await e.tick();assert.equal(form.hasAttribute('data-uncertain'),true);
  e.submit(form);await e.tick();assert.equal(e.calls.length,1);assert.equal(e.moves.some(x=>x[0]==='assign'),false);
});

test('new release redirects using GET after a successful POST',async()=>{
  const e=environment();e.responder=async()=>({url:'https://store.test/pedido/receipt',status:200,headers:{get(){return 'text/html';}},text:async()=>JSON.stringify({path:'/pedido/receipt',revision:'new-release'})});
  e.submit(new e.Form('https://store.test/pedido/nuevo'));await e.tick();
  assert.deepEqual(e.moves.at(-1),['assign','https://store.test/pedido/receipt']);assert.equal(e.calls.length,1);
});

test('later navigation wins and canceled GET never replaces it',async()=>{
  const e=environment();
  e.responder=(href,options)=>new Promise((resolve,reject)=>{
    options.signal.addEventListener('abort',()=>reject(Object.assign(new Error(),{name:'AbortError'})));
    if(href.endsWith('/carrito'))resolve({url:href,status:200,headers:{get(){return 'text/html';}},text:async()=>JSON.stringify({path:'/carrito'})});
  });
  e.click(e.link('https://store.test/catalogo'));e.click(e.link('https://store.test/carrito'));await e.tick();
  assert.equal(e.path,'/carrito');assert.equal(e.moves.some(x=>x[0]==='assign'),false);
});

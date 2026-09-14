// Protocol and click regression tests without external browser dependencies.
// Run: node tests/test_frontends.js
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
class Element {
  constructor() { this.children = []; this.style = {}; this.classList = {add(){}}; }
  set innerHTML(value) { this.children = []; }
  appendChild(child) { this.children.push(child); }
  addEventListener(type, fn) { this['on'+type] = fn; }
  getBoundingClientRect() { return {height: 460}; }
}
for (const counter of [false, true]) {
  const folder = path.join(__dirname, '..', counter ? 'counter_board_frontend' : 'chess_board_frontend');
  const html = fs.readFileSync(path.join(folder, 'index.html'), 'utf8');
  assert(!html.includes('saved from url='));
  const el = new Element(), events = {}, messages = [];
  const ctx = {document:{getElementById(){return el},createElement(){return new Element()},body:new Element()},
    parent:{postMessage(msg){messages.push(msg)}},addEventListener(type,fn){events[type]=fn},
    requestAnimationFrame(fn){fn()},ResizeObserver:class {observe(){}},prompt(){return 'Q'}};
  ctx.window = ctx;vm.createContext(ctx);
  for (const script of html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)) vm.runInContext(script[1],ctx);
  const args = {fen:counter?'rntbkqbinr/pppppppppp/10/10/10/10/PPPPPPPPPP/RNTBKQBINR w KQkq - 0 1':'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',orientation:'white',interactive:true,legal_moves:['e2e4']};
  const render = () => events.message({data:{type:'streamlit:render',args}});
  render();assert.equal(el.children.length,counter?80:64);
  if(counter) for(const sq of el.children) for(const child of sq.children) if(child.src) assert(fs.existsSync(path.join(folder,child.src)));
  const click = coord => {const squares=vm.runInContext(counter?'squares()':'displaySquares(state.orientation)',ctx);el.children[squares.indexOf(coord)].onclick({preventDefault(){},stopPropagation(){}})};
  click('e2');render(); // Polling must preserve selection between clicks.
  click('e4');click('e4');
  const moves=messages.filter(m=>m.type==='streamlit:setComponentValue');
  assert.equal(moves.length,1);assert.equal(moves[0].value.move,'e2e4');assert.equal(moves[0].dataType,'json');
  args.orientation='black';args.interactive=false;render();
  assert.equal(vm.runInContext(counter?'squares()[0]':'displaySquares(state.orientation)[0]',ctx), counter?'j1':'h1');
  console.log((counter?'10x8':'8x8')+': board, assets, polling, move protocol and orientation OK');
}

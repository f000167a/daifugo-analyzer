const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// Minimal DOM/timer harness. Tests control flow, not rendering or browser layout.
function ui() {
  const html=fs.readFileSync(path.join(__dirname,'..','index.html'),'utf8');
  const nodes=new Map(), timers=new Map();
  let timerId=0, now=0;
  function element(tag='div') {
    const node={tag,children:[],style:{},dataset:{},disabled:false,hidden:false,checked:false,
      textContent:'',className:'',listeners:{},_value:'',_html:'',
      append(...items){items.forEach(item=>this.appendChild(item));},
      appendChild(item){
        this.children.push(item);
        if(this.tag==='select' && (!this._value||item.selected)) this._value=String(item.value);
      },
      addEventListener(event,fn){(this.listeners[event]??=[]).push(fn);},
      dispatch(event){for(const fn of this.listeners[event]||[]) fn();},
      scrollIntoView(){},
    };
    Object.defineProperties(node,{
      id:{set(value){this._id=value;nodes.set(value,this);},get(){return this._id;}},
      value:{set(value){this._value=String(value);},get(){return this._value;}},
      innerHTML:{set(value){this._html=value;this.children=[];if(this.tag==='select')this._value='';},get(){return this._html;}},
    });
    return node;
  }
  for(const match of html.matchAll(/<([\w-]+)\b[^>]*\bid="([^"]+)"[^>]*>/g)) {
    const node=element(match[1]);node.id=match[2];
    node.checked=/\bchecked\b/.test(match[0]);node.hidden=/\bhidden\b/.test(match[0]);
  }
  nodes.get('numP').value='3';
  const app=vm.createContext({
    document:{getElementById:id=>nodes.get(id)||null,createElement:element,querySelectorAll:()=>[]},
    performance:{now:()=>now+=3},console,
    setTimeout:fn=>{const id=++timerId;timers.set(id,fn);return id;},
    clearTimeout:id=>timers.delete(id),
  });
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],app);
  const flushOne=()=>{const next=timers.entries().next().value;if(next){timers.delete(next[0]);next[1]();}};
  const flushAll=()=>{let count=0;while(timers.size){assert.ok(++count<5000,'timer loop did not finish');flushOne();}};
  const evaluate=code=>vm.runInContext(code,app);
  return {app,nodes,timers,flushOne,flushAll,evaluate,
    setPlayers(np,size){nodes.get('numP').value=np;app.buildPosOpts();nodes.get('numP').dispatch('change');if(size)nodes.get('handCount').value=size;},
  };
}

test('Incorrect initial size is rejected before starting any computation',()=>{
  const u=ui();u.app.run();
  assert.match(u.nodes.get('runStatus').textContent,/18枚/);
  assert.equal(u.nodes.get('runBtn').disabled,false);
  assert.equal(u.timers.size,0);
});

test('Random hand respects every selected player count and hand size',()=>{
  const u=ui();
  for(const [np,size] of [[3,18],[4,13],[4,14],[5,10],[5,11]]){
    u.setPlayers(np,size);
    for(let i=0;i<30;i++){u.app.randHand();assert.equal(u.nodes.get('tot').textContent,size);}
  }
});

test('Cancel prevents queued results and a new run can finish',()=>{
  const u=ui();u.app.randHand();u.app.simOnce=()=>1;
  u.app.run();u.flushOne();u.app.cancelRun();u.flushAll();
  assert.equal(u.evaluate('SIM_LOG.length'),0);
  assert.equal(u.nodes.get('result').style.display,'none');
  assert.equal(u.nodes.get('runBtn').disabled,false);
  assert.equal(u.nodes.get('cancelBtn').hidden,true);
  assert.match(u.nodes.get('runStatus').textContent,/中止/);
  u.app.run();u.flushAll();
  assert.equal(u.evaluate('SIM_LOG.length'),1);
  assert.equal(u.nodes.get('result').style.display,'block');
});

test('Repeated run clicks do not create duplicate jobs or logs',()=>{
  const u=ui();u.app.randHand();let calls=0;u.app.simOnce=()=>{calls++;return 1;};
  u.app.run();u.app.run();u.app.run();u.flushAll();
  assert.equal(calls,2000);assert.equal(u.evaluate('SIM_LOG.length'),1);
});

for(const id of ['numP','myPos','handCount','r8','rRev','rMCTS']){
  test(`Changing ${id} cancels a running job and hides completed results`,()=>{
    const u=ui();u.app.randHand();u.app.simOnce=()=>1;
    u.app.run();u.flushOne();u.nodes.get(id).dispatch('change');u.flushAll();
    assert.equal(u.evaluate('SIM_LOG.length'),0);
    assert.equal(u.nodes.get('runBtn').disabled,false);
    u.app.run();u.flushAll();assert.equal(u.evaluate('SIM_LOG.length'),1);
    u.nodes.get(id).dispatch('change');
    assert.equal(u.nodes.get('result').style.display,'none');
    assert.equal(u.nodes.get('gameplan').style.display,'none');
    assert.match(u.nodes.get('runStatus').textContent,/もう一度/);
  });
}

test('Editing cards or dealing again invalidates ongoing work',()=>{
  const u=ui();u.app.randHand();u.app.simOnce=()=>1;
  u.app.run();u.flushOne();u.app.chg(3,1,4);u.flushAll();
  assert.equal(u.evaluate('SIM_LOG.length'),0);
  u.app.randHand();u.app.run();u.flushOne();u.app.randHand();u.flushAll();
  assert.equal(u.evaluate('SIM_LOG.length'),0);
});

test('An engine error restores controls, leaves no fake result, and allows retry',()=>{
  const u=ui();u.app.randHand();u.app.simOnce=()=>{throw Error('test failure');};
  u.app.run();u.flushAll();
  assert.match(u.nodes.get('runStatus').textContent,/test failure/);
  assert.equal(u.nodes.get('runBtn').disabled,false);
  assert.equal(u.nodes.get('cancelBtn').hidden,true);
  assert.equal(u.evaluate('SIM_LOG.length'),0);
  u.app.simOnce=()=>1;u.app.run();u.flushAll();
  assert.equal(u.evaluate('SIM_LOG.length'),1);
});

test('Result and log use the captured role and show model limitations',()=>{
  const u=ui();u.app.randHand();u.nodes.get('myPos').value='富豪';u.app.simOnce=()=>1;
  u.app.run();
  // Programmatic changes without a UI change event must not relabel the running snapshot.
  u.nodes.get('myPos').value='貧民';u.flushAll();
  assert.equal(u.evaluate('SIM_LOG[0].config.myPos'),'富豪');
  assert.match(u.nodes.get('modeChip').textContent,/富豪/);
  assert.match(u.nodes.get('modelNote').textContent,/モデル内の推定/);
  assert.match(u.nodes.get('modelNote').textContent,/±2.2ポイント/);
});

test('Real 2000-trial run completes with finite rates and an intact input snapshot',()=>{
  const u=ui();u.setPlayers(5,11);u.app.randHand();
  const before=u.evaluate('JSON.stringify(HC)');
  u.app.run();u.flushAll();
  assert.equal(u.evaluate('SIM_LOG.length'),1);
  assert.equal(u.evaluate('JSON.stringify(HC)'),before);
  assert.equal(u.evaluate('SIM_LOG[0].config.trials'),2000);
  const rates=u.evaluate('Object.values(SIM_LOG[0].rates)');
  for(const rate of rates) assert.ok(Number.isFinite(rate)&&rate>=0&&rate<=100);
  assert.ok(Math.abs(rates.reduce((a,b)=>a+b,0)-100)<=0.3);
});

// Inspect generated user-visible copy without relying on browser layout.
function advice(u,{np=3,p1=20,pLast=20,hand={3:2,4:2,5:2,9:1},r8=true,rRev=true,pos='平民0'}={}){
  const rates={1:p1,[np]:pLast};
  u.app.renderAdv(rates,np,hand,r8,rRev,null,pos);
  u.app.renderGamePlan(rates,np,hand,r8,rRev,pos);
  const text=id=>u.nodes.get(id).children.map(node=>node.innerHTML).join('\n').replace(/<[^>]*>/g,'');
  return {adv:text('adv'),plan:text('gameplan')};
}

for(const [np,baseline] of [[3,'33.3'],[4,'25'],[5,'20']]){
  test(`Advice uses the ${np}-player uniform baseline without population-percentile claims`,()=>{
    const u=ui(),base=100/np;
    const cases=[
      [0.4,'弱い手','比較基準を大きく下回る'],
      [0.7,'やや弱い手','比較基準を下回る'],
      [1.0,'基準付近の手','比較基準に近い'],
      [1.2,'やや強い手','比較基準をやや上回る'],
      [1.5,'強い手','比較基準を上回る'],
      [1.9,'非常に強い手','比較基準を大きく上回る'],
    ];
    for(const [multiple,label,comparison] of cases){
      const {adv,plan}=advice(u,{np,p1:base*multiple,pLast:base/2});
      assert.ok(adv.includes(`${np}人戦で全員の1位率が同じなら${baseline}%（100÷${np}人）`));
      assert.match(adv,/均等な比較基準/);
      assert.match(adv,/実際の手札分布の平均や上位何割かを示すものではない/);
      assert.match(adv,/選択したルール・配札仮定・AIによるモデル内の目安/);
      assert.match(adv,/実戦の勝率を保証しない/);
      assert.match(plan,/手札の強さ判定（モデル内の目安）/);
      assert.ok(plan.includes(`${label}　${comparison}・1位率`));
      assert.doesNotMatch(adv+plan,/平均(?:は)?30%|上位1割クラス|上位2〜3割の好手|平均並み|平均より/);
    }
  });
}

for(const rRev of [false,true]){
  test(`Eight-cut copy describes lead, equal counts, finishing, and revolution=${rRev}`,()=>{
    const u=ui();
    for(const np of [3,4,5]) for(const count of [1,2,3,4]){
      const {adv,plan}=advice(u,{np,rRev,hand:{3:2,4:2,5:2,8:count,16:1}});
      assert.match(adv,/場が空なら8を親出しできる/);
      assert.match(adv,/場に重ねるときは同じ枚数が必要/);
      assert.match(adv,/通常時は3〜7/);
      if(rRev) assert.match(adv,/革命中は9・10・J・Q・K・A・2/);
      else assert.doesNotMatch(adv,/革命中は/);
      assert.match(adv,/手札が残っていれば自分の手番が続く/);
      assert.match(adv,/8で上がった場合は次の人の手番になる/);
      assert.doesNotMatch(adv+plan,/7以下|低カードを出した隙|8切り後/);
    }
  });
}

test('Advice does not recommend eight-cut when disabled or when no eight is held',()=>{
  const u=ui();
  for(const np of [3,4,5]) for(const rRev of [false,true]){
    for(const [r8,count] of [[false,0],[false,1],[false,2],[true,0]]){
      // Covers default/strong priority, high-last-place priority, and defensive paragraph.
      for(const [winMultiple,lastMultiple] of [[0.4,0.5],[0.8,1.1],[0.8,1.4],[1.0,0.5],[1.5,0.5],[1.9,0.5]]){
        const {adv,plan}=advice(u,{np,r8,rRev,p1:100/np*winMultiple,pLast:100/np*lastMultiple,
          hand:{3:2,4:2,5:2,8:count,9:1}});
        assert.doesNotMatch(adv+plan,/8切り/);
      }
    }
  }
});

test('Two-card advice never recommends 2-on-2 and distinguishes normal and revolution strength',()=>{
  const u=ui();
  for(const np of [3,4,5]) for(const rRev of [false,true]) for(const count of [1,2,4]){
    for(const [winMultiple,lastMultiple] of [[0.4,0.5],[1.5,0.5],[0.4,1.5]]){
      const {adv,plan}=advice(u,{np,rRev,p1:100/np*winMultiple,pLast:100/np*lastMultiple,
        hand:{3:2,9:2,15:count}});
      for(const text of [adv,plan]){
        assert.match(text,/通常時に(?:最強の数字札|強い)/);
        assert.match(text,/2同士やJKRには返せない/);
        if(rRev) assert.match(text,/革命中の2は最も弱い数字札/);
        else assert.doesNotMatch(text,/革命中の2/);
        assert.doesNotMatch(text,/相手が2で上がりを狙うタイミング|2枚は最強/);
      }
      assert.match(adv,/同じ枚数で、現在の強さ順でより強い組/);
      assert.match(adv,/同じ強さでは返せない/);
    }
  }
});

test('Triple advice permits legal responses as well as leading, for weak and strong hands',()=>{
  const u=ui();
  for(const rRev of [false,true]) for(const p1 of [10,65]){
    const {adv}=advice(u,{rRev,p1,hand:{7:3,9:2,15:1}});
    assert.match(adv,/3枚組は親出しでき/);
    assert.match(adv,/場が3枚組なら現在の強さ順で勝てる場合にも返せる/);
    assert.doesNotMatch(adv,/自分でリードしないと出せず|相手に同じ手がなければほぼ通る/);
  }
});

test('Two jokers alone do not imply a playable pair or two different revolutions',()=>{
  const u=ui();
  for(const rRev of [false,true]){
    const {adv}=advice(u,{rRev,hand:{7:2,9:2,16:2}});
    assert.match(adv,/JKR2枚だけのペアは出せず/);
    assert.match(adv,/同じJKRには返せない/);
    assert.match(adv,/補完した組はその数字の強さで判定/);
  }
  for(const hand of [{7:3,9:1,16:2},{7:3,9:3,16:2}]){
    const {adv}=advice(u,{hand,rRev:true});
    assert.match(adv,/3枚組にJKRを1枚補完して革命を狙える/);
    assert.match(adv,/別々の3枚組が2種あれば、それぞれに1枚ずつ補完/);
    assert.doesNotMatch(adv,/革命×2候補|2種の革命をJKR補完で狙える/);
  }
});

test('Four-card and ace-group advice states the required counts and conditional return',()=>{
  const u=ui();
  const noTempo=advice(u,{hand:{7:4,9:1},rRev:true}).adv;
  assert.match(noTempo,/場が流れなければ、相手が逆転後により強い4枚組/);
  const {adv}=advice(u,{hand:{7:4,9:4,15:1},rRev:true});
  assert.match(adv,/4枚組を出すと必ず革命になる/);
  assert.match(adv,/現在の強さ順で強い組があれば返せる/);
  assert.match(adv,/4枚を出すたびに強さが再び逆転/);
  assert.doesNotMatch(adv,/革命返し可|そのまま出してもそこそこ強い/);
  assert.doesNotMatch(advice(u,{hand:{7:4,9:4,15:1},rRev:false}).adv,/4枚組を出すと必ず革命/);
  for(const count of [2,3,4]){
    assert.match(advice(u,{hand:{7:2,14:count}}).adv,/ペアは2枚、トリプルは3枚必要（不足分はJKRで補完可能）/);
  }
});

test('Two jokers are not counted as an additional natural pair in advice',()=>{
  const {adv}=advice(ui(),{np:5,hand:{3:2,4:2,5:2,6:2,16:2}});
  assert.match(adv,/ペア×4/);
  assert.doesNotMatch(adv,/ペア×5|ペアは5種|ペアが豊富（5種）/);
  assert.match(adv,/JKR2枚だけのペアは出せず/);
});

test('Revolution advice distinguishes low ranks and does not reuse consumed cards',()=>{
  const u=ui();
  const mixed=advice(u,{np:5,hand:{3:4,9:2,15:4}}).adv;
  assert.match(mixed,/3は低い数字/);
  assert.doesNotMatch(mixed,/3・2は低い数字/);
  const used=advice(u,{np:5,hand:{3:4,6:2,7:2,9:2}}).plan;
  assert.match(used,/革命に出したカードは手札に残らない/);
  assert.match(used,/残った手札のうち小さい数字ほど強くなる/);
  assert.doesNotMatch(used,/その3が手番を握る/);
});

test('Revolution advice does not tell the player to dispose of the required high-rank group first',()=>{
  const u=ui();
  for(const pos of ['平民0','富豪','貧民']) for(const rank of [13,14,15]) for(const jokers of [0,1]){
    const label={13:'K',14:'A',15:'2'}[rank];
    const {plan}=advice(u,{np:5,pos,p1:5,hand:{3:2,6:2,7:2,[rank]:4-jokers,16:jokers}});
    assert.doesNotMatch(plan,new RegExp(`${label}(?:などの上位カード)?を先に(?:消化|処理)`));
    assert.doesNotMatch(plan,/上位カードを(?:先に)?整理しながら/);
  }
  // Unrelated high cards can still be listed; the candidate K group is preserved.
  assert.match(advice(u,{np:5,p1:5,hand:{3:2,6:2,13:4,14:2}}).plan,/Aを先に処理/);
});

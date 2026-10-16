const test = require('node:test');
const assert = require('node:assert/strict');
const {loadApp, hand, seeded, plain} = require('./load-app.cjs');
const app = loadApp();
const deck = Array.from({length:52}, (_,i)=>3+Math.floor(i/4)).concat(16,16);
const sum = h => Object.values(h).reduce((a,b)=>a+b,0);

for(const rev of [false,true]) {
  test(`Joker is strictly stronger than every natural card; revolution=${rev}`,()=>{
    for(let n=3;n<=15;n++) assert.ok(app.rk(16,rev)>app.rk(n,rev));
    for(let n=3;n<15;n++) assert.equal(app.rk(n,rev)<app.rk(n+1,rev),!rev);
  });
  test(`Joker cannot overcall Joker; revolution=${rev}`,()=>{
    assert.equal(app.cpOk(16,1,[16,1],rev),false);
    assert.equal(app.pick(hand([16]),[16,1],rev,[1,1],true),null);
    assert.equal(app.pick(hand([3]),[16,1],rev,[1,1],true),null);
    assert.equal(app.mctsPick(hand([16]),[16,1],rev,[1,1],true,true,3,
      [hand([16]),hand([3]),hand([4])],0,0,[0,1,2]),null);
  });
}

test('Equal count and strict higher rank are required',()=>{
  assert.equal(app.cpOk(5,2,[4,1],false),false);
  assert.equal(app.cpOk(5,2,[5,2],false),false);
  assert.equal(app.cpOk(5,2,[4,2],false),true);
  assert.equal(app.cpOk(4,2,[5,2],true),true);
});

test('Joker complements can lead pairs and triples without revolution enabled',()=>{
  assert.deepEqual(plain(app.pick(hand([13,16]),null,false,[5,5],false)),[13,2,1]);
  assert.deepEqual(plain(app.pick(hand([13,16,16]),null,false,[5,5],false)),[13,3,2]);
  assert.deepEqual(plain(app.moveSizes(3,1,null)),[{sz:1,jUsed:0},{sz:2,jUsed:0},{sz:3,jUsed:0},{sz:4,jUsed:1}]);
});

for(const [np,size] of [[3,18],[4,13],[4,14],[5,10],[5,11]]) {
  test(`Balanced ${np}-player deal with ${size}-card player hand conserves every rank`,()=>{
    for(let seed=0;seed<100;seed++) {
      const rng=seeded(seed);
      const mine=hand(app.shuf([...deck],rng).slice(0,size));
      const before=JSON.stringify(mine);
      const players=app.dealHands(mine,np,rng);
      assert.equal(players.length,np);
      assert.equal(sum(players[0]),size);
      assert.equal(JSON.stringify(mine),before);
      assert.equal(players.reduce((t,h)=>t+sum(h),0),54);
      for(const h of players) assert.ok([Math.floor(54/np),Math.ceil(54/np)].includes(sum(h)));
      for(let n=3;n<=16;n++) assert.equal(players.reduce((t,h)=>t+h[n],0),n===16?2:4);
    }
  });
  test(`Seeded games finish with legal moves, conserved cards, turns and ranks: ${np}/${size}`,()=>{
    for(let seed=0;seed<30;seed++) for(const r8 of [false,true]) for(const rRev of [false,true]) {
      const rng=seeded(seed);
      const mine=hand(app.shuf([...deck],rng).slice(0,size));
      let previous=null, played=0;
      const rank=app.simOnce(mine,np,r8,rRev,'平民0',false,rng,event=>{
        if(previous) {
          const expected=plain(previous.players);
          if(previous.play) {
            const [n,sz,j]=previous.play;
            if(n===16) expected[previous.pid][16]-=sz;
            else {expected[previous.pid][n]-=sz-j; expected[previous.pid][16]-=j;}
          }
          assert.deepEqual(plain(event.players),expected);
        }
        assert.equal(event.players.reduce((t,h)=>t+sum(h),0)+played,54);
        for(const h of event.players) for(const c of Object.values(h)) assert.ok(Number.isInteger(c)&&c>=0);
        if(event.finished) {
          assert.deepEqual([...event.ranks].sort(),Array.from({length:np},(_,i)=>i));
          assert.ok(event.turn<54*np+np);
          for(const pid of event.ranks.slice(0,-1)) assert.equal(sum(event.players[pid]),0);
          return;
        }
        if(previous) {
          const [n,sz]=previous.play||[];
          const finished=previous.play && sum(event.players[previous.pid])===0;
          const reset=finished || (r8&&n===8);
          assert.equal(event.rev,sz===4&&rRev ? !previous.rev : previous.rev);
          if(reset) assert.equal(event.field,null);
          if(r8&&n===8&&!finished) assert.equal(event.pid,previous.pid);
          if(finished) assert.ok(!event.active.includes(previous.pid));
        }
        if(event.play) {
          const [n,sz,j]=event.play, h=event.players[event.pid];
          assert.ok(app.cpOk(n,sz,event.field,event.rev));
          assert.ok(sz>=1&&sz<=4);
          if(n===16) {assert.equal(sz,1);assert.equal(j,0);assert.ok(h[16]>=1);}
          else {assert.ok(sz-j>=1);assert.ok(h[n]>=sz-j);assert.ok(h[16]>=j);}
          played+=sz;
        } else assert.notEqual(event.field,null);
        previous=plain(event);
      });
      assert.ok(rank>=1&&rank<=np);
    }
  });
}

test('Invalid counts, ranks, player counts, totals and selected hand sizes are rejected',()=>{
  const good=hand(deck.slice(0,13));
  assert.throws(()=>app.validateHand({...good,16:3},4));
  for(const c of [-1,0.5,NaN,Infinity,'1',5]) assert.throws(()=>app.validateHand({...good,3:c},4));
  assert.throws(()=>app.validateHand({...good,17:0},4));
  assert.throws(()=>app.validateHand(good,2));
  assert.throws(()=>app.validateHand(hand([]),3));
  assert.throws(()=>app.validateHand(good,4,14));
  assert.throws(()=>app.dealHands(hand([16,16,16]),3));
  assert.doesNotThrow(()=>app.validateHand(good,4,13));
});

test('Only the explicitly entered 富豪 role receives a rank penalty',()=>{
  const mine=hand(deck.slice(0,18));
  let lowerRanks=0;
  for(let seed=0;seed<30;seed++) {
    const baseline=app.simOnce(mine,3,true,true,'平民0',false,seeded(seed));
    if(baseline>1) lowerRanks++;
    for(const role of ['平民','貧民']) assert.equal(app.simOnce(mine,3,true,true,role,false,seeded(seed)),baseline);
    assert.equal(app.simOnce(mine,3,true,true,'富豪',false,seeded(seed)),baseline===1?1:3);
  }
  assert.ok(lowerRanks>0);
});

test('A seed reproduces the entire game without mutating the input',()=>{
  const mine=hand(deck.slice(0,18)), before=JSON.stringify(mine);
  const traces=[];
  for(let i=0;i<2;i++) {
    const events=[];
    app.simOnce(mine,3,true,true,'平民0',false,seeded(123),e=>events.push(plain(e)));
    traces.push(events);
  }
  assert.deepEqual(traces[0],traces[1]);
  assert.equal(JSON.stringify(mine),before);
});

test('Incomplete simulations fail explicitly instead of inventing seat-order ranks',()=>{
  const broken=loadApp(); broken.pick=()=>null;
  assert.throws(()=>broken.simOnce(hand(deck.slice(0,18)),3,true,true,'平民0',false,seeded(1)),/場が空/);
  assert.throws(()=>broken.mctsRollout([hand([3]),hand([4])],0,2,true,true,null,false,0,[0,1],0),/場が空/);
});

test('All other players passing returns an empty table to the last player',()=>{
  const fixture=loadApp(), fields=[];
  fixture.pick=(h,field,rev)=>{
    fields.push(field&&[...field]);
    for(let n=3;n<=16;n++) if(h[n]>0&&fixture.cpOk(n,1,field,rev)) return [n,1,0];
    return null;
  };
  assert.equal(fixture.mctsRollout([hand([7,9]),hand([3]),hand([4])],0,3,false,false,null,false,0,[0,1,2],0),1);
  assert.deepEqual(plain(fields.slice(0,4)),[null,[7,1],[7,1],null]);
});

test('8-cut keeps the turn; finishing clears the table for the next active player',()=>{
  const fixture=loadApp(), seen=[];
  fixture.pick=(h,field,rev)=>{
    seen.push({cards:Object.keys(h).filter(n=>h[n]>0).map(Number),field:field&&[...field]});
    for(let n=3;n<=16;n++) if(h[n]>0&&fixture.cpOk(n,1,field,rev)) return [n,1,0];
    return null;
  };
  fixture.mctsRollout([hand([8,9]),hand([3,15]),hand([4,16])],0,3,true,false,null,false,0,[0,1,2],0);
  assert.deepEqual(plain(seen.slice(0,3)),[
    {cards:[8,9],field:null},{cards:[9],field:null},{cards:[3,15],field:null},
  ]);
});

test('Four cards reverse strength only when revolution is enabled',()=>{
  for(const enabled of [false,true]) {
    const fixture=loadApp(), seen=[];
    fixture.pick=(h,field,rev)=>{
      seen.push({field:field&&[...field],rev});
      if(h[7]===3&&h[16]===1) return [7,4,1];
      for(let n=3;n<=16;n++) if(h[n]>0&&fixture.cpOk(n,1,field,rev)) return [n,1,0];
      return null;
    };
    fixture.mctsRollout([hand([7,7,7,16,9]),hand([3]),hand([4])],0,3,false,enabled,null,false,0,[0,1,2],0);
    assert.deepEqual(plain(seen[1]),{field:[7,4],rev:enabled});
  }
});

test('Experimental lookahead also completes legal seeded games',()=>{
  for(const np of [3,4,5]) for(let seed=0;seed<3;seed++) {
    const rng=seeded(seed),mine=hand(app.shuf([...deck],rng).slice(0,Math.ceil(54/np)));
    const rank=app.simOnce(mine,np,true,true,'平民0',true,rng,event=>{
      if(event.finished) {assert.equal(event.ranks.length,np);return;}
      if(event.play) assert.ok(app.cpOk(event.play[0],event.play[1],event.field,event.rev));
      for(const h of event.players) for(const c of Object.values(h)) assert.ok(c>=0);
    });
    assert.ok(rank>=1&&rank<=np);
  }
});

test('A non-pass lookahead candidate clears the prior consecutive pass count',()=>{
  const fixture=loadApp(), calls=[];
  fixture.mctsRollout=(players,myIdx,np,r8,rRev,field,rev,cp)=>{
    calls.push({field:field&&[...field],cp});return 2;
  };
  const mine=hand([7,9,16]);
  fixture.mctsPick(mine,[5,1],false,[3,3],true,true,3,
    [mine,hand([3,10,12]),hand([4,11,15])],0,1,[0,1,2]);
  assert.ok(calls.some(c=>c.field));
  assert.ok(calls.some(c=>!c.field));
  for(const call of calls) assert.equal(call.cp,0);
});

for(const [np,size] of [[4,13],[5,11]]) {
  test(`Initial simulation deal is balanced: ${np} players, input ${size}`,()=>{
    const fixture=loadApp(), seen=new Set(), sizes=[];
    const realPick=fixture.pick;
    fixture.pick=(h,...args)=>{
      if(!seen.has(h)){seen.add(h);sizes.push(sum(h));}
      return realPick(h,...args);
    };
    fixture.simOnce(hand(deck.slice(0,size)),np,false,false,'平民0',false,seeded(1));
    assert.equal(sizes.length,np);
    assert.ok(sizes.every(n=>n>=Math.floor(54/np)&&n<=Math.ceil(54/np)),`initial sizes: ${sizes}`);
    assert.equal(sizes.reduce((a,b)=>a+b,0),54);
  });
}

for(const rev of [false,true]){
  test(`Advice legality: equal ranks, including 2-on-2, cannot overcall; revolution=${rev}`,()=>{
    for(let rank=3;rank<=16;rank++) for(let size=1;size<=4;size++){
      assert.equal(app.cpOk(rank,size,[rank,size],rev),false);
    }
    for(let size=1;size<=4;size++){
      const mine=hand(Array(size).fill(15));
      assert.equal(app.pick(mine,[15,size],rev,[3,3],true),null);
      assert.equal(app.mctsPick(mine,[15,size],rev,[3,3],true,true,3,
        [mine,hand([3,4,5]),hand([6,7,8])],0,0,[0,1,2]),null);
    }
  });

  test(`Advice legality: triples may respond to weaker triples but not pairs; revolution=${rev}`,()=>{
    const mine=hand([7,7,7]), weaker=rev?8:6;
    assert.deepEqual(plain(app.pick(mine,[weaker,3],rev,[3,3],true)),[7,3,0]);
    assert.equal(app.pick(mine,[7,3],rev,[3,3],true),null);
    // A response to a pair must be a pair, not the entire triple.
    const pairResponse=app.pick(mine,[weaker,2],rev,[3,3],true);
    if(pairResponse) assert.equal(pairResponse[1],2);
  });

  test(`Advice legality: jokers need a natural rank for groups and retain its strength; revolution=${rev}`,()=>{
    const jokers=hand([16,16]), weaker=rev?8:6;
    assert.equal(app.pick(jokers,[7,2],rev,[3,3],true),null);
    assert.equal(app.mctsPick(jokers,[7,2],rev,[3,3],true,true,3,
      [jokers,hand([3,4,5]),hand([6,7,8])],0,0,[0,1,2]),null);
    assert.deepEqual(plain(app.pick(jokers,null,rev,[3,3],true)),[16,1,0]);
    assert.equal(app.pick(hand([7,16]),[7,2],rev,[3,3],true),null);
    assert.deepEqual(plain(app.pick(hand([7,16]),[weaker,2],rev,[3,3],true)),[7,2,1]);
  });
}

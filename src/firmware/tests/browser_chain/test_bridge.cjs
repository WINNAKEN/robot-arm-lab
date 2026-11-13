'use strict';
const {spawnSync}=require('node:child_process'),assert=require('node:assert/strict');const exe=process.argv[2];let checks=0;const ok=(v,m)=>{++checks;assert.ok(v,m);};
const b='b'.repeat(32),a='a'.repeat(32),d='d'.repeat(32);
const lines=['M','J '+d,'J '+a,'N '+b+' 0 v1|11|1|1|1|stop|0|0|1|0|0','N '+d+' 0 v1|11|1|1|1|maintenance|0|0|1|0|0','M','W 10','P'];
const r=spawnSync(exe,['1'],{input:lines.join('\n')+'\n',encoding:'utf8'});ok(r.status===0,'native public API');const rows=r.stdout.trim().split('\n').map(JSON.parse);
ok(rows[0].at==='0'&&rows[0].paired_mask===0&&rows[0].moves===0,'cold no bootstrap/pair');ok(rows[1].wire_error===2,'pair actually authenticated');ok(rows[2].paired&&rows[2].credential===b,'actual session credential');ok(rows[3].wire_error===12,'listener independent from opcode');ok(rows[4].wire_error===2,'actual command auth');ok(rows[5].at==='0'&&rows[5].paired_mask===1&&rows[5].moves===0,'no internal clock advancement/renew/move');ok(rows[6].at==='10'&&rows[7].at==='10','clock drives actual Owner');
const back=spawnSync(exe,['1'],{input:'W 10\nW 9\n',encoding:'utf8'});ok(back.status===3,'clock reversal rejected');
console.log('CHAIN BRIDGE PASS checks='+checks+'; actual Owner cold/pair/auth/listener/time; no hardware');

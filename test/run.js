const assert = require('assert');
const { load, world, rootDrive } = require('./mock');
const { products } = require('./products');
const api = load();
let igCalls = [], aiCalls = 0, aiReply = null;
world.now = new Date('2026-10-12T02:00:00Z'); // 月曜 11:00 JST
world.fetch = (url, opt) => {
  if (url.includes('/products.json')) return { body: { products } };
  if (url.includes('api.anthropic.com')) { aiCalls++; return { body: { content: [{ type: 'text', text: JSON.stringify(aiReply(JSON.parse(opt.payload))) }] } }; }
  if (url.includes('drive.google.com/thumbnail') || url.includes('/img/')) return { bytes: Buffer.from('img'), body: '', headers: { 'Content-Type': 'image/jpeg' } };
  if (url.includes('graph.instagram.com')) { igCalls.push(url.split('?')[0].replace(/.*v26\.0\//, '') + (opt.method ? ' POST' : ' GET'));
    if (url.includes('refresh_access_token')) return { body: { access_token: 'NEW', expires_in: 5184000 } };
    if (url.includes('/me?')) return { body: { id: '42', user_id: '1789', username: 'basshu_japan', account_type: 'BUSINESS' } };
    if (url.includes('content_publishing_limit')) return { body: { data: [{ quota_usage: 0 }] } };
    if (world.igDeny && /\/media$/.test(url) && !url.includes('/' + world.igDeny + '/')) return { code: 400, body: { error: { message: 'Application does not have permission for this action', code: 10 } } };
    if (/\/media$/.test(url)) { assert.strictEqual(opt.payload.media_type, 'REELS'); assert.ok(/^https:\/\/.+\.mp4$/.test(opt.payload.video_url)); return { body: { id: '555' } }; }
    if (url.includes('/555?')) return { body: { status_code: 'FINISHED' } };
    if (/media_publish$/.test(url)) return { body: { id: '999' } };
    if (url.includes('/999?')) return { body: { permalink: 'https://www.instagram.com/reel/abc/' } };
  }
  throw new Error('想定外のURL: ' + url);
};
const T = k => api.table_(k).rows;
const ok = m => console.log('  ✓ ' + m);
const P = h => T('prod').find(r => r.handle === h);
const setP = (h, o) => { const t = api.table_('prod'); const r = t.rows.find(x => x.handle === h); Object.assign(r, o); t.sh.getRange(r._row, 1, 1, t.head.length).setValues([t.head.map(k => r[k] === undefined ? '' : r[k])]); };
const subs = f => f.folders.map(x => x.name).sort();

assert.strictEqual(api.limitHashtags_('本文です。\n\n#a #b ＃c #d #e #f #g', 5), '本文です。\n\n#a #b ＃c #d #e'); assert.strictEqual(api.limitHashtags_('タグなし', 5), 'タグなし');
console.log('1. 準備、商品名の読み取り、選んだ商品だけのフォルダ');
api.setup();
const root = rootDrive.folders[0];
assert.strictEqual(root.name, 'BasShu投稿素材');
assert.strictEqual(T('prod').length, 8);
assert.deepStrictEqual(root.folders.map(f => f.name), ['季節の暮らし'], '最初は商品フォルダを作らない');
const show = h => [P(h)['表示名'], P(h)['色・種類'], P(h)['季節'], P(h)['分類']];
assert.deepStrictEqual(show('gauze-red-m'), ['Gauze Blanket', 'RED (M)', '通年', 'ガーゼブランケット'], '【WEB限定】は動画に出さない');
assert.deepStrictEqual(show('beads-moss').slice(0, 2), ['BEADS CUSHION', 'MOSS GREEN 専用カバー']);
assert.deepStrictEqual(show('feather-olive').slice(0, 2), ['Long Feather Cushion', 'OLIVE'], '*の注記は出さない');
assert.deepStrictEqual(show('wool-blanket-brown').slice(0, 3), ['NEW Wool Blanket', 'BROWN', '秋冬']);
assert.strictEqual(P('igusa-orange')['季節'], '春夏'); assert.strictEqual(P('wool-blanket-brown')['価格'], '¥19,800');
assert.strictEqual(P('apron-brown')['在庫'], false);
setP('wool-blanket-brown', { 'フォルダを作る': true }); setP('cushion-sax', { 'フォルダを作る': 'TRUE' });
api.syncProducts();
assert.deepStrictEqual(root.folders.map(f => f.name).sort(), ['Cushion Cover / SAX', 'NEW Wool Blanket / BROWN', '季節の暮らし'].sort());
root.folders.forEach(f => assert.deepStrictEqual(subs(f), ['使用済み', '未使用', '次に使う'].sort()));
api.syncProducts(); assert.strictEqual(T('prod').length, 8); assert.strictEqual(root.folders.length, 3);
assert.strictEqual(world.triggers.length, 2);
ok('商品8件、チェックした2商品だけフォルダと3つの小フォルダ、再同期で増えない');

console.log('2. 素材も使用シーンの写真もない → ディテール型で静かに作る');
world.props.PILLAR_IDX = '0';
let id = api.makeNow();
let row = T('log').find(r => r.ID === id);
assert.strictEqual(row['テンプレート'], 'detail'); assert.strictEqual(row.handle, 'wool-blanket-brown', '10月は秋冬の商品から');
assert.ok(!world.mails.some(m => m.subject.includes('素材がありません')), '知らせのメールは出さない');
assert.ok(row['メモ'].includes('AI未設定') && row['メモ'].includes('ディテール型'));
assert.ok(row['キャプション'].includes('#basshu'));
ok('フォルダが空でも止まらない');

console.log('2b. フォルダのない商品も、サイトの写真で作る');
{ setP('gauze-red-m', { '使用シーンの写真番号': 3, '寄りの写真番号': 3 });
  world.props.PILLAR_IDX = '0'; world.mails.length = 0;
  const jid = api.makeNow(); const jr = T('log').find(r => r.ID === jid); const sp = JSON.parse(jr['設定JSON']);
  assert.strictEqual(jr['テンプレート'], 'slide'); assert.strictEqual(jr.handle, 'gauze-red-m'); assert.ok(!P('gauze-red-m')['フォルダID']);
  assert.ok(sp.files.wear_image.url.includes('gauze-red-m2')); { const u = Object.values(sp.files).map(f => f.url); assert.strictEqual(new Set(u).size, u.length, '同じ写真は使わない'); }
  assert.strictEqual(sp.config.ai_image, false); assert.strictEqual(sp.config.name, 'Gauze Blanket'); assert.strictEqual(world.mails.length, 0); assert.ok(jr['メモ'].includes('サイトの写真'));
  setP('gauze-red-m', { '使用シーンの写真番号': '', '寄りの写真番号': 2 });
  // AIに番号を提案させる
  world.props.ANTHROPIC_API_KEY = 'k'; aiReply = req => ({ n: req.messages[0].content.filter(x => x.type === 'image').length >= 4 ? 2 : 0 });
  api.suggestScenePhotos();
  assert.strictEqual(P('gauze-red-m')['使用シーンの写真番号'], 2); assert.strictEqual(P('feather-olive')['使用シーンの写真番号'], 0, '該当なしは0を入れ、次回は判定しない');
  const n = aiCalls; api.suggestScenePhotos(); assert.strictEqual(aiCalls, n, '判定済みはやり直さない');
  delete world.props.ANTHROPIC_API_KEY; }
ok('サイトの写真で作成(札なし)、AIによる写真番号の提案');

console.log('3. 柱を順に回す(AIあり、素材あり)');
world.props.ANTHROPIC_API_KEY = 'k'; world.props.PILLAR_IDX = '0';
const fCushion = root.folders.find(f => f.name.includes('Cushion Cover'));
const u = fCushion.folders.find(f => f.name === '未使用');
const a = u.add('a.jpg', 'image/jpeg'), b = u.add('b.png', 'image/png'); u.add('memo.heic', 'image/heic');
const fBlanket = root.folders.find(f => f.name.includes('Wool Blanket'));
const vid = fBlanket.folders.find(f => f.name === '未使用').add('実写_広げる.mp4', 'video/mp4');
fBlanket.folders.find(f => f.name === '未使用').add('big.mov', 'video/quicktime', Buffer.alloc(31 * 1024 * 1024));
let sawImages = 0, sawPrompt = '';
aiReply = req => { const c = req.messages[0].content; sawImages = c.filter(x => x.type === 'image').length; sawPrompt = c[c.length - 1].text;
  return { pick: 2, copy: '重ねた色の、静かな深み。', caption: '朝の空気が冷たくなってきました。\n大阪・忠岡町で織り上げた一枚です。\n\n商品名\nプロフィールのリンクからご覧いただけます\n\n#basshu #インテリア雑貨 #ブランケット #ウールブランケット #冬支度 #暮らしの道具 #ひざ掛け', tagline: '昔からそこにあったように', copy_lines: ['ひざに掛けると', 'ふわりと空気を含む', 'ふっくらとした風合い', '4行目は捨てる'], point_lines: '大阪・忠岡町の工場で\n丁寧に織り上げました', point: 'ウール100%の一枚', notice_title: '名前の由来', notice_lines: ['由来は「播州」', '先染めの糸で織る'] }; };
const ids = [], seen = [];
for (let i = 0; i < 5; i++) { id = api.makeNow(); ids.push(id); row = T('log').find(r => r.ID === id); const spec = JSON.parse(row['設定JSON']);
  seen.push(row['柱'] + ':' + row['テンプレート'] + ':' + row.handle);
  { const u = Object.values(spec.files).map(f => f.url).filter(Boolean); assert.strictEqual(new Set(u).size, u.length, '同じ写真を2回使わない: ' + row['テンプレート']); }
  setP(row.handle, { '最終投稿日': new Date(world.now.getTime() + i * 1000) });
  if (i === 0) { assert.strictEqual(spec.config.price, '', '価格は出さない'); assert.deepStrictEqual(spec.config.copy_lines, ['ひざに掛けると', 'ふわりと空気を含む', 'ふっくらとした風合い']); assert.deepStrictEqual(spec.config.point_lines, ['大阪・忠岡町の工場で', '丁寧に織り上げました']); assert.strictEqual(spec.config.tagline, '昔からそこにあったように'); assert.strictEqual((row['キャプション'].match(/#/g) || []).length, 5, 'ハッシュタグは5個に削る'); assert.ok(row['キャプション'].includes('#冬支度') && !row['キャプション'].includes('#ひざ掛け'));
    assert.ok(sawPrompt.includes('【文章の方針】') && sawPrompt.includes('3〜5文') && sawPrompt.includes('Cushion Cover / SAX') && sawPrompt.includes('柱の方針') && sawPrompt.includes('BasShu'), '方針と商品説明がAIに渡る');
    assert.strictEqual(row.handle, 'cushion-sax', '直近に出した商品を避け、素材のある商品を選ぶ'); assert.strictEqual(spec.files.wear_image.drive_id, b.id, 'AIが2番を選ぶ'); assert.strictEqual(sawImages, 4, '候補2+商品+寄りを見て書く'); assert.strictEqual(spec.config.ai_image, true); assert.strictEqual(spec.config.brand, 'BasShu'); }
  if (i === 1) { assert.strictEqual(spec.config.template, 'zoom'); assert.strictEqual(spec.files.wear_image.drive_id, vid.id, '動画が優先される'); assert.strictEqual(spec.config.ai_image, false, '実写_は札なし'); assert.strictEqual(sawImages, 3); assert.ok(sawPrompt.includes('忠岡町'), '商品説明がAIに渡る'); }
  if (i === 2) { assert.strictEqual(row['柱'], '色と柄の話'); assert.deepStrictEqual(spec.config.copy_lines, []); assert.deepStrictEqual(spec.config.notice_lines, ['由来は「播州」', '先染めの糸で織る']); assert.ok(!spec.files.wear_image); assert.ok(sawPrompt.includes('播州')); }
  if (i === 3) { assert.strictEqual(row['柱'], '育っていくもの'); assert.ok(!spec.files.wear_image, 'AI画像は使わない'); assert.ok(/使い込|育て/.test(P(row.handle)['説明']), '説明に「育つ」話がある商品を選ぶ'); assert.strictEqual(sawImages, 3); assert.ok(spec.files.extra_image.url !== spec.files.detail_image.url && spec.files.extra_image.url !== spec.files.product_image.url); assert.ok(sawPrompt.includes('想像で描写しない')); }
}
console.log('    ' + seen.join('\n    '));
{ const bi = ids.map(x => JSON.parse(T('log').find(r => r.ID === x)['設定JSON']).config.bgm_index); for (let i = 1; i < bi.length; i++) assert.strictEqual(bi[i], bi[i - 1] + 1, '曲の番号が1つずつ進む'); }
assert.deepStrictEqual(seen.map(s => s.split(':')[1]), ['slide', 'zoom', 'notice', 'detail', 'slide']);
assert.ok(!seen.some(s => s.includes('apron')), '在庫切れは選ばない'); assert.ok(!seen.some(s => s.includes('igusa')), '10月に春夏の商品は選ばない');
assert.strictEqual(world.props.PILLAR_IDX, '0');
ok('5つの柱が順に回る、動画優先、AIのトンマナ選択、HEICと30MB超は対象外、在庫切れと季節外を除外');

console.log('4. 動画づくりとの受け渡し');
const key = world.props.WEBAPP_KEY;
assert.strictEqual(JSON.parse(api.doGet({ parameter: { action: 'peek', key: 'x' } }).text).error, 'forbidden');
const pending = JSON.parse(api.doGet({ parameter: { action: 'peek', key } }).text).pending; assert.strictEqual(pending, 7);
const job = JSON.parse(api.doGet({ parameter: { action: 'job', key } }).text);
assert.ok(job.id && /^\d{8}-[0-9a-f]{40}\.mp4$/.test(job.file_name) && job.config.template);
assert.strictEqual(JSON.parse(api.doGet({ parameter: { action: 'peek', key } }).text).pending, 6);
const fileRes = JSON.parse(api.doGet({ parameter: { action: 'file', key, id: a.id } }).text); assert.strictEqual(fileRes.name, 'a.jpg');
world.mails.length = 0;
api.doPost({ postData: { contents: JSON.stringify({ key, action: 'done', id: ids[1], video_url: 'https://u.github.io/basshu-reel/v/x.mp4' }) } });
assert.ok(world.mails[0].subject.includes('【BasShu投稿】') && world.mails[0].subject.includes('投稿候補ができました') && world.mails[0].body.includes('?t=' + ids[1]));
assert.strictEqual(api.doGet({ parameter: { t: ids[1] } }).token, ids[1]);
ok('合言葉なしは拒否、注文の受け渡し、完了でスタッフにメール');

console.log('5. 投稿する');
let r = api.publish(ids[1], 'テスト'); assert.ok(!r.ok && r.message.includes('未設定'));
assert.strictEqual(api.getReview(ids[1]).state, '確認待ち');
world.props.IG_TOKEN = 'T'; api.testInstagram(); assert.strictEqual(world.props.IG_USER_ID, '1789');
r = api.publish(ids[1], 'よい品です\n#a #b #c #d #e #f'); assert.ok(!r.ok && r.message.includes('5個まで'));
for (const bad of ['免疫力が上がります', '抗菌防臭の生地です', '天然の空気清浄機', 'よく眠れます', '消臭にも']) { r = api.publish(ids[1], bad); assert.ok(!r.ok && r.message.includes('使えない表現'), bad); }
assert.strictEqual(api.ngHits_('使い込むほど、風合いが育つ。手ざわりのよい後染めのキルト。先染めの糸で織る播州織。熊本県八代産のい草。').length, 0, 'ふつうの文は止めない');
igCalls = [];
r = api.publish(ids[1], '重ねた色の、静かな深み。\n#basshu'); assert.ok(r.ok, r.message);
assert.deepStrictEqual(igCalls, ['me/media POST', '555 GET', 'me/media_publish POST', '999 GET']);
const rv = api.getReview(ids[1]); assert.strictEqual(rv.state, '投稿済み'); assert.strictEqual(rv.permalink, 'https://www.instagram.com/reel/abc/');
assert.strictEqual(vid.parent.name, '使用済み'); assert.strictEqual(vid.parent.parent, fBlanket); assert.strictEqual(a.parent.name, '未使用'); assert.strictEqual(b.parent.name, '未使用');
r = api.publish(ids[1], 'もう一度'); assert.ok(!r.ok, '二重投稿しない');
ok('未接続と禁止表現は止める、Instagramへの4手順、素材を使用済みへ、二重投稿なし');

{ world.igDeny = '1789'; world.log = false; api.diagInstagram(); assert.strictEqual(world.props.IG_PATH, '1789');
  api.doPost({ postData: { contents: JSON.stringify({ key, action: 'done', id: ids[2], video_url: 'https://u.github.io/basshu-reel/v/w.mp4' }) } });
  igCalls = []; const r2 = api.publish(ids[2], '播州織の話。\n#basshu'); assert.ok(r2.ok, r2.message); assert.strictEqual(igCalls[0], '1789/media POST');
  world.igDeny = 'none'; delete world.props.IG_PATH; api.diagInstagram(); assert.ok(!world.props.IG_PATH);
  const r3 = api.publish(ids[1], 'x'); assert.ok(!r3.ok);
  world.igDeny = ''; }
ok('診断で通る指定を見つけて保存');

console.log('6. 見送る → 別の素材で作り直し');
api.doPost({ postData: { contents: JSON.stringify({ key, action: 'done', id: ids[0], video_url: 'https://u.github.io/basshu-reel/v/y.mp4' }) } });
const before = T('log').length;
r = api.skip(ids[0]); assert.ok(r.ok);
const remake = T('log')[before]; assert.strictEqual(remake['テンプレート'], 'slide'); assert.notStrictEqual(remake['素材ID'], b.id); assert.ok(remake['素材ID']); assert.ok(remake['メモ'].includes('見送りの作り直し'));
assert.strictEqual(b.parent.name, '未使用');
ok('見送った素材を避けて作り直す(素材は未使用に残る)');

console.log('7. 失敗の通知、催促、接続の自動延長、お知らせの差し込み、月・水・金');
world.mails.length = 0;
api.doPost({ postData: { contents: JSON.stringify({ key, action: 'failed', id: ids[3], error: 'cannot identify image file' }) } });
assert.ok(world.mails[0].subject.includes('動画を作れませんでした') && world.mails[0].to.includes('owner@example.com'));
api.doPost({ postData: { contents: JSON.stringify({ key, action: 'done', id: ids[4], video_url: 'https://u.github.io/basshu-reel/v/z.mp4' }) } });
world.now = new Date(world.now.getTime() + 26 * 3600000); world.mails.length = 0; igCalls = [];
api.dailyChores();
assert.ok(world.mails.some(m => m.subject.includes('確認をお願いします'))); assert.strictEqual(world.props.IG_TOKEN, 'NEW');
assert.ok(world.mails.some(m => m.body.includes('動画がまだできていません')));
world.mails.length = 0; api.dailyChores(); assert.ok(!world.mails.some(m => m.subject.includes('確認をお願いします')), '催促は1回だけ');
api.table_('news').sh.appendRow(['年末年始のご案内', '12月26日 午前までのご注文は', '年内に発送いたします', 'Wool Blanket', '']);
const pi = world.props.PILLAR_IDX; id = api.makeNow(); row = T('log').find(x => x.ID === id); const sp = JSON.parse(row['設定JSON']);
assert.strictEqual(row['柱'], 'お知らせ'); assert.strictEqual(sp.config.notice_title, '年末年始のご案内'); assert.ok(row['商品名'].includes('Wool Blanket')); assert.strictEqual(world.props.PILLAR_IDX, pi);
const nid2 = api.makeNow(); assert.notStrictEqual(T('log').find(x => x.ID === nid2)['柱'], 'お知らせ', 'お知らせは1回だけ');
api.doPost({ postData: { contents: JSON.stringify({ key, action: 'done', id, video_url: 'https://u.github.io/basshu-reel/v/n.mp4' }) } });
const nb = T('log').length; assert.ok(api.skip(id).ok); assert.strictEqual(T('log')[nb]['柱'], 'お知らせ', '見送りの作り直しもお知らせ');
world.now = new Date('2026-10-15T02:00:00Z'); const n0 = T('log').length; api.scheduledCreate(); assert.strictEqual(T('log').length, n0, '木曜は作らない');
world.now = new Date('2026-10-16T02:00:00Z'); api.scheduledCreate(); assert.strictEqual(T('log').length, n0 + 1, '金曜は作る');
world.now = new Date('2026-10-19T02:00:00Z'); api.scheduledCreate(); assert.strictEqual(T('log').length, n0 + 2, '月曜は作る');
ok('失敗メール、催促は1回、接続の延長、お知らせ優先、月・水・金だけ作成');

console.log('8. 「次に投稿する」で商品を指名する');
for (const idx of ['0', '2', '3']) {
  setP('igusa-orange', { '次に投稿する': true }); world.props.PILLAR_IDX = idx;
  id = api.makeNow(); row = T('log').find(x => x.ID === id); const s8 = JSON.parse(row['設定JSON']);
  assert.strictEqual(row.handle, 'igusa-orange', '季節外でもフォルダなしでも、指名した商品で作る(柱' + idx + ')'); assert.ok(row['メモ'].includes('次に投稿する'));
  if (idx === '0') { assert.strictEqual(row['テンプレート'], 'slide'); assert.ok(s8.files.wear_image.url.includes('igusa-orange'), 'サイトの写真を使う'); }
  assert.strictEqual(P('igusa-orange')['次に投稿する'], false, '指名は1回で外れる');
}
id = api.makeNow(); assert.notStrictEqual(T('log').find(x => x.ID === id).handle, 'igusa-orange', '次の回は通常の順番に戻る');
ok('指名した商品が最優先、使ったらチェックが外れる');

console.log('9. 同じ分類が続かない');
{ const cat = h => (P(h) || {})['分類']; const last = T('log').slice(-6).map(x => cat(x.handle));
  world.props.PILLAR_IDX = '3'; const seq = []; for (let i = 0; i < 4; i++) { world.props.PILLAR_IDX = '3'; id = api.makeNow(); const h = T('log').find(x => x.ID === id).handle; seq.push(cat(h)); setP(h, { '最終投稿日': new Date(world.now.getTime() + i * 1000) }); }
  for (let i = 1; i < seq.length; i++) assert.notStrictEqual(seq[i], seq[i - 1], '分類が連続: ' + seq.join(' → '));
  console.log('    ' + seq.join(' → ')); }
ok('直近と同じ分類を避ける');
console.log('\nすべて通りました');

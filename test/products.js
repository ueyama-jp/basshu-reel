const img = (h, n) => Array.from({ length: n }, (_, i) => ({ src: `http://127.0.0.1:8765/img/${i === 0 ? 'product' : 'detail'}_placeholder.jpg?p=${h}${i}` }));
const P = (handle, title, vendor, n, body, available) => ({ handle, title, vendor, product_type: 'LIVING', body_html: `<p>${body || title}です。</p>`, variants: [{ title: 'Default Title', price: '19800.00', available: available !== false }], images: img(handle, n) });
module.exports = { products: [
  P('wool-blanket-brown', 'NEW Wool Blanket / BROWN', 'ウールブランケット', 6, '大阪府忠岡町の老舗工場で丁寧に織り上げた一枚。使いながら育てるウールブランケット'),
  P('wool-blanket-border', 'Wool Blanket / Border MULTI 2', 'ウールブランケット', 5),
  P('gauze-red-m', '【WEB限定】Gauze Blanket / RED (M)', 'ガーゼブランケット', 4, '使い込むほど、カラダに馴染む4重ガーゼブランケット'),
  P('igusa-orange', 'IGUSA RUG / ORANGE', 'い草ラグ', 6, '熊本県八代産のい草。染め上げられたい草の自然な色合い'),
  P('cushion-sax', 'Cushion Cover / SAX', 'クッション・カバー', 4),
  P('beads-moss', 'BEADS CUSHION / MOSS GREEN【専用カバー】', 'ビーズクッション・カバー', 7, '唯一無二の生地の風合い'),
  P('apron-brown', 'Check Apron / BROWN', 'エプロン', 2, '播州織の生地を使ったチェック柄のエプロン', false),
  P('feather-olive', '【WEB限定】Long Feather Cushion / OLIVE*クッション付き', 'クッション・ビーズクッション', 2),
] };

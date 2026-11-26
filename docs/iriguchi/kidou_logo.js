/* MadbroLab 起動ロゴの部品 KidouLogo（Web 用・1.0.0・2026-11-26 SE室。ひな型＝言霊 KOTODAMA）
   全社の製品が、この1つを写して使う。ほかの物に寄りかからない（読むだけで動く・見た目も中に入っている・外から何も取り寄せない）。
   形：深い色の地に細い線の窓。「ウェーン」と1本の光の線が横に伸び、窓が上下に開く → 文字が一字ずつ走って出る
       （製品の名前と読み＝大／頭文字の正式名＝小／MadbroLab＝さらに小）→ 計器の数字と帯が流れる → 相棒が一言名乗る（文字）→ 消える。
       全部で約1.9秒。押さなくても消える。
   雰囲気（fuun）は3つ。動きの順・秒数・3段の並びは3つとも同じ：
     kinmirai  ＝近未来（既定）。少し先の未来の機械の起動画面。青白い光。
     ken_mahou ＝剣と魔法の世界の相棒の案内の窓。金の細い二重線・星の印・光の輪。
     koutetsu  ＝鋼鉄の機械・システム。鉄の板の地・太い枠と鋲・区切りの計器・機械仕掛けの開き方。
   守る事：アプリを起こした時の1回だけ（同じページで2回呼んでも1回）／指は全部すり抜けて下の画面（録音の丸など）に届く／
          どこかに触れた・キーを押したら、その場で消える／音は出さない／絵は使わない（文字と線と光だけ）／端末に元からある書体だけ。
   呼び方（製品ごとに変えるのは、名前・読み・正式名・名乗り・色1つ。雰囲気は fuun の1語）：
     KidouLogo.dasu({namae:"言霊", yomi:"KOTODAMA",
                     seishiki:"Keyword-Oriented Transcription & Output Document Automated Management Archive",
                     nanori:"言霊、起動。", fuun:"kinmirai", iro:"#8FD8FF"});
   nanori を省くと「<namae>、起動。」。fuun を省くと kinmirai。iro を省くと雰囲気ごとの色（近未来＝青白・剣と魔法＝金・鋼鉄＝琥珀）。
   使う人が選ぶ口（1.1.0）：KidouLogo.erabu("ken_mahou") でその端末に覚える（localStorage madbro_kidou_fuun）。覚えた物は fuun の設定より先。
     KidouLogo.erabu("") で忘れる＝製品の設定に戻る。KidouLogo.erabareta() は覚えた物（無ければ ""）。KidouLogo.namae[f] は3択に出す名前。
   近未来の上の帯は、会社がこの先も動き続けている事を伝える一言 MIRAI をゆっくり流す（全社で同じ字）。 */
(function (W) {
  "use strict";
  if (W.KidouLogo) return;
  var D = W.document, VER = "1.1.0", ID = "mbkKidou", KIOKU = "madbro_kidou_fuun";
  var MIRAI = "次の時代へ同期中 ─ CONTINUING";   // 近未来の上の帯の一言（Android の MIRAI と同じ字）
  var NAMAE = { kinmirai: "近未来", ken_mahou: "剣と魔法の相棒", koutetsu: "鋼鉄の機械" };   // 使う人の3択に出す名前
  var NAGASA = 1900;                       // 全部の長さ（ミリ秒）。動きの秒数は全部ここと下の表だけ
  var BAN = {   // 一字ずつ走る所：[始まり, 長さ]（ミリ秒）
    mei: [300, 260], yomi: [380, 380], sei: [480, 520], lab: [700, 260], nanori: [1060, 300], hed: [140, 220]
  };
  function r(n) { return Math.floor(Math.random() * n); }
  function hex4() { return "0x" + ("000" + r(65536).toString(16).toUpperCase()).slice(-4); }
  function nagare(f, n) { var s = [], i; for (i = 0; i < (n || 18); i++) s.push(f(i)); s = s.join("") ; return s + s; }   // 2つ並べて半分ずらすと、切れ目なく流れる
  // 雰囲気ごとの違い（字・数字の出し方・色）。見た目の違いは下の CSS の .f-<名前>
  var FUUN = {
    kinmirai: { iro: "#8FD8FF", mae: "» ", chira: "アイウエオカキクケコサシスセソ0123456789ABCDEF#%&*+=<>/",
      hed: function (y) { return "SYS.BOOT // " + y; },
      kei: function () { return hex4() + " / " + hex4(); },
      obi: function () { return nagare(function (i) { return (i % 3 === 0 ? hex4() : i % 3 === 1 ? (Math.random() * 100).toFixed(2) : "CH" + ("0" + (i % 12 + 1)).slice(-2) + " SYNC") + "  │  "; }); },
      ue: function () { return nagare(function () { return MIRAI + "  │  " + hex4() + "  │  "; }, 6); } },   // 上の帯＝会社がこの先も続いていく一言
    ken_mahou: { iro: "#E8C77A", mae: "◆ ", chira: "✦✧·*+◇◆†‡§",
      hed: function (y) { return "✧ 相棒の窓 ─ " + y; },
      kei: function () { return "MP " + (100 + r(900)) + " / 999"; },
      obi: function () { var w = ["INVOCATIO", "VERBUM", "ANIMA", "LUX", "FIDES", "MEMORIA", "VOX", "SAPIENTIA"];
        return nagare(function (i) { return (i % 2 ? w[r(w.length)] : ["I", "II", "III", "IV", "V", "VI", "VII", "IX", "XII"][r(9)]) + "  ✦  "; }); } },
    koutetsu: { iro: "#F2A93B", mae: "> ", chira: "0123456789#=/|-+",
      hed: function (y) { return "MACHINE " + y + " ─ SELF CHECK"; },
      kei: function () { return "PSI " + (120 + Math.random() * 20).toFixed(1) + " / " + (23.5 + Math.random()).toFixed(1) + "V"; },
      obi: function () { return nagare(function (i) { return ["PRESS " + (100 + Math.random() * 3).toFixed(1) + "kPa", "TEMP " + (35 + Math.random() * 3).toFixed(1) + "°C",
        "RPM " + (1100 + r(300)), "VOLT " + (23.5 + Math.random()).toFixed(1) + "V", "TORQ " + (80 + r(20)) + "%"][i % 5] + "  ┃  "; }); } }
  };
  var deta = false, root = null, raf = 0, owari = 0, t0 = 0, hashiri = [], kazu = null, kei = null, F = FUUN.kinmirai;

  var P = "#" + ID, MONO = "ui-monospace,'SF Mono',Menlo,Consolas,'Roboto Mono',monospace";
  var MIN = "'Hiragino Mincho ProN','Yu Mincho','YuMincho','Noto Serif JP','Noto Serif CJK JP',serif";
  var CSS = [
    P + "{position:fixed;inset:0;z-index:2147483600;pointer-events:none;overflow:hidden;background:#03070D;color:#EAF7FF;",
    "  font-family:system-ui,-apple-system,'Hiragino Sans','Yu Gothic UI','Noto Sans JP','Noto Sans CJK JP',sans-serif;",
    "  -webkit-font-smoothing:antialiased;display:flex;align-items:center;justify-content:center;animation:mbk-de 1900ms linear both}",
    P + " *{pointer-events:none;box-sizing:border-box;margin:0}",
    P + " .mbk-hikari{position:absolute;inset:0;background:radial-gradient(60% 45% at 50% 50%,rgba(var(--mbk),.16),transparent 70%),",
    "  repeating-linear-gradient(0deg,rgba(255,255,255,.028) 0 1px,transparent 1px 3px)}",
    P + " .mbk-obi{position:absolute;left:0;right:0;height:16px;overflow:hidden;opacity:.5;",
    "  font:9px/16px " + MONO + ";color:rgba(var(--mbk),.9);white-space:nowrap;",
    "  border-top:1px solid rgba(var(--mbk),.22);border-bottom:1px solid rgba(var(--mbk),.22);animation:mbk-obi-de 500ms 100ms ease-out both}",
    P + " .mbk-obi span{display:inline-block;animation:mbk-nagare 2400ms linear both}",
    P + " .mbk-obi.mbk-shita span{animation-direction:reverse}",
    P + " .mbk-ue{top:12%}" + P + " .mbk-shita{bottom:12%}",
    // 近未来の上の帯（MIRAI）：読めるように明るく・少し大きく・ゆっくり流す
    P + ".f-kinmirai .mbk-ue{font-size:10.5px;color:rgba(var(--mbk),1);animation-name:mbk-obi-de2}" + P + ".f-kinmirai .mbk-ue span{animation-duration:9000ms}",
    P + " .mbk-wa{display:none}",
    P + " .mbk-mado{position:relative;width:min(88vw,400px);padding:14px 18px 12px;text-align:center;",
    "  border:1px solid rgba(var(--mbk),.38);background:linear-gradient(rgba(var(--mbk),.05),rgba(var(--mbk),.02));",
    "  box-shadow:0 0 24px rgba(var(--mbk),.12),inset 0 0 24px rgba(var(--mbk),.06);animation:mbk-hiraku 300ms 200ms cubic-bezier(.2,.8,.2,1) both}",
    P + " .mbk-sen{position:absolute;left:0;right:0;margin:0 auto;width:min(96vw,448px);top:50%;height:1px;background:rgba(var(--mbk),1);",
    "  box-shadow:0 0 8px rgba(var(--mbk),1),0 0 20px rgba(var(--mbk),.7);animation:mbk-sen 520ms 40ms cubic-bezier(.3,.9,.3,1) both;opacity:0}",
    P + " .mbk-k{position:absolute;width:12px;height:12px;border:0 solid rgba(var(--mbk),.95)}",
    P + " .mbk-k1{left:-1px;top:-1px;border-left-width:2px;border-top-width:2px}",
    P + " .mbk-k2{right:-1px;top:-1px;border-right-width:2px;border-top-width:2px}",
    P + " .mbk-k3{left:-1px;bottom:-1px;border-left-width:2px;border-bottom-width:2px}",
    P + " .mbk-k4{right:-1px;bottom:-1px;border-right-width:2px;border-bottom-width:2px}",
    P + " .mbk-hed{display:flex;justify-content:space-between;gap:8px;font:8.5px/1 " + MONO + ";white-space:nowrap;",
    "  letter-spacing:.12em;color:rgba(var(--mbk),.8);padding-bottom:8px;border-bottom:1px solid rgba(var(--mbk),.18)}",
    P + " .mbk-hikaru{text-shadow:0 0 6px rgba(var(--mbk),.85),0 0 18px rgba(var(--mbk),.45)}",
    P + " .mbk-mei{font-family:" + MIN + ";font-weight:600;",
    "  font-size:clamp(52px,20vw,96px);line-height:1.1;letter-spacing:.12em;padding-left:.12em;margin-top:10px}",
    P + " .mbk-yomi{font-size:clamp(14px,4.4vw,19px);font-weight:600;letter-spacing:.6em;padding-left:.6em;margin-top:2px;",
    "  animation:mbk-hirogaru 700ms 380ms cubic-bezier(.2,.8,.2,1) both}",
    P + " .mbk-sei{font-size:clamp(8.5px,2.5vw,10.5px);line-height:1.5;letter-spacing:.04em;color:rgba(234,247,255,.78);margin:10px auto 0;max-width:30em}",
    P + " .mbk-lab{font-size:8px;letter-spacing:.42em;padding-left:.42em;color:rgba(var(--mbk),.75);margin-top:9px}",
    P + " .mbk-gauge{position:relative;height:2px;margin:12px 0 7px;background:rgba(var(--mbk),.15)}",
    P + " .mbk-gauge b{position:absolute;left:0;top:0;bottom:0;width:100%;background:rgba(var(--mbk),.95);box-shadow:0 0 6px rgba(var(--mbk),.9);",
    "  animation:mbk-gauge 1000ms 260ms cubic-bezier(.4,.1,.3,1) both}",
    P + " .mbk-shita2{display:flex;justify-content:space-between;align-items:baseline;gap:8px;",
    "  font:8.5px/1 " + MONO + ";color:rgba(var(--mbk),.75);letter-spacing:.1em}",
    P + " .mbk-nanori{font-family:inherit;font-size:12px;letter-spacing:.14em;color:#EAF7FF;text-align:left}",
    P + " .mbk-nanori i{display:inline-block;width:.55em;height:1em;vertical-align:-2px;margin-left:2px;background:rgba(var(--mbk),.95);",
    "  animation:mbk-tenmetsu 300ms steps(1) infinite}",
    P + " .mbk-mada{visibility:hidden}",

    // ---- 剣と魔法の世界の相棒（ken_mahou）：深い藍の地・金の細い二重線・星の印・広がる光の輪・字は全部明朝と飾りのある洋字 ----
    P + ".f-ken_mahou{background:#0B0816;color:#FBF3DF;font-family:'Iowan Old Style','Palatino Linotype','Book Antiqua',Palatino,Georgia," + MIN + "}",
    P + ".f-ken_mahou .mbk-hikari{background:radial-gradient(55% 40% at 50% 50%,rgba(var(--mbk),.14),transparent 72%),",
    "  radial-gradient(circle at 50% 50%,rgba(70,40,120,.35),transparent 75%)}",
    P + ".f-ken_mahou .mbk-obi{font-family:inherit;font-size:9.5px;letter-spacing:.18em;border-color:rgba(var(--mbk),.3);opacity:.45}",
    P + ".f-ken_mahou .mbk-wa{display:block;position:absolute;left:50%;top:50%;width:min(130vw,600px);aspect-ratio:1;margin-left:calc(min(130vw,600px) / -2);",
    "  margin-top:calc(min(130vw,600px) / -2);border-radius:50%;border:1px solid rgba(var(--mbk),.35);",
    "  box-shadow:0 0 0 6px rgba(var(--mbk),.04),0 0 0 7px rgba(var(--mbk),.22),inset 0 0 30px rgba(var(--mbk),.12);animation:mbk-wa 1500ms 60ms cubic-bezier(.2,.8,.2,1) both}",
    P + ".f-ken_mahou .mbk-mado{border-color:rgba(var(--mbk),.6);background:linear-gradient(rgba(30,20,50,.75),rgba(15,10,30,.75));",
    "  box-shadow:0 0 0 4px #0B0816,0 0 0 5px rgba(var(--mbk),.35),0 0 30px rgba(var(--mbk),.15)}",
    P + ".f-ken_mahou .mbk-k{border:0;width:auto;height:auto;font:13px/1 serif;color:rgba(var(--mbk),1);text-shadow:0 0 8px rgba(var(--mbk),.9)}",
    P + ".f-ken_mahou .mbk-k::before{content:'\\2726'}",
    P + ".f-ken_mahou .mbk-k1{left:-7px;top:-8px}" + P + ".f-ken_mahou .mbk-k2{right:-7px;top:-8px}",
    P + ".f-ken_mahou .mbk-k3{left:-7px;bottom:-8px}" + P + ".f-ken_mahou .mbk-k4{right:-7px;bottom:-8px}",
    P + ".f-ken_mahou .mbk-hed{font-family:inherit;font-size:10px;letter-spacing:.16em;border-bottom-style:double;border-bottom-width:3px;border-color:rgba(var(--mbk),.3)}",
    P + ".f-ken_mahou .mbk-yomi{font-family:inherit;font-weight:700}",
    P + ".f-ken_mahou .mbk-sei{font-style:italic;color:rgba(251,243,223,.8)}",
    P + ".f-ken_mahou .mbk-lab{font-family:inherit;font-size:8.5px}",
    P + ".f-ken_mahou .mbk-gauge{height:1px}",
    P + ".f-ken_mahou .mbk-shita2{font-family:inherit;font-size:10px}",
    P + ".f-ken_mahou .mbk-nanori{color:#FBF3DF;font-family:" + MIN + "}",
    P + ".f-ken_mahou .mbk-nanori i{width:2px}",

    // ---- 鋼鉄の機械（koutetsu）：鉄の板の地（細い縦の筋）・太い二重の枠と鋲・区切りの計器・機械仕掛けにカクカク開く ----
    P + ".f-koutetsu{background:linear-gradient(#1B1E21,#0C0E10);color:#DDE2E7}",
    P + ".f-koutetsu .mbk-hikari{background:repeating-linear-gradient(90deg,rgba(255,255,255,.022) 0 1px,transparent 1px 4px),",
    "  radial-gradient(60% 45% at 50% 50%,rgba(var(--mbk),.08),transparent 70%)}",
    P + ".f-koutetsu .mbk-obi{height:18px;line-height:18px;font-weight:700;color:rgba(200,206,212,.75);border-width:2px;border-color:rgba(160,168,176,.3);",
    "  background:rgba(0,0,0,.25)}",
    P + ".f-koutetsu .mbk-mado{border:2px solid rgba(176,184,192,.6);background:linear-gradient(#272B2F,#191C1F);",
    "  box-shadow:inset 0 0 0 4px #1D2024,inset 0 0 0 5px rgba(176,184,192,.22),0 6px 24px rgba(0,0,0,.6);",
    "  animation:mbk-hiraku 320ms 200ms steps(6,end) both}",
    P + ".f-koutetsu .mbk-sen{height:3px;box-shadow:0 0 6px rgba(var(--mbk),.8)}",
    P + ".f-koutetsu .mbk-k{border:0;width:auto;height:auto;font:7px/1 sans-serif;color:rgba(150,158,166,.9)}",
    P + ".f-koutetsu .mbk-k::before{content:'\\25CF'}",
    P + ".f-koutetsu .mbk-k1{left:6px;top:6px}" + P + ".f-koutetsu .mbk-k2{right:6px;top:6px}",
    P + ".f-koutetsu .mbk-k3{left:6px;bottom:6px}" + P + ".f-koutetsu .mbk-k4{right:6px;bottom:6px}",
    P + ".f-koutetsu .mbk-hed{font-weight:700;color:rgba(var(--mbk),.95);border-bottom:2px solid rgba(176,184,192,.25);margin:0 6px}",
    P + ".f-koutetsu .mbk-hikaru{text-shadow:0 1px 0 #000,0 -1px 0 rgba(255,255,255,.12)}",
    P + ".f-koutetsu .mbk-mei{font-family:'Hiragino Sans','Yu Gothic','Noto Sans JP','Noto Sans CJK JP',sans-serif;font-weight:900;color:#E4E8EC}",
    P + ".f-koutetsu .mbk-yomi{font-family:" + MONO + ";font-weight:800;color:rgba(var(--mbk),1);text-shadow:0 0 6px rgba(var(--mbk),.5)}",
    P + ".f-koutetsu .mbk-sei{font-family:" + MONO + ";font-size:clamp(8px,2.3vw,9.5px);text-transform:uppercase;color:rgba(200,206,212,.7)}",
    P + ".f-koutetsu .mbk-lab{font-family:" + MONO + ";font-weight:700;color:rgba(200,206,212,.6)}",
    P + ".f-koutetsu .mbk-gauge{height:7px;margin:12px 6px 7px;background:rgba(0,0,0,.45);box-shadow:inset 0 0 0 1px rgba(176,184,192,.25)}",
    P + ".f-koutetsu .mbk-gauge b{top:1px;bottom:1px;left:1px;box-shadow:none;",
    "  background:repeating-linear-gradient(90deg,rgba(var(--mbk),1) 0 9px,transparent 9px 11px);animation-timing-function:steps(12,end)}",
    P + ".f-koutetsu .mbk-shita2{font-weight:700;margin:0 6px}",
    P + ".f-koutetsu .mbk-nanori{font-weight:700;color:rgba(var(--mbk),1);text-shadow:0 0 6px rgba(var(--mbk),.6)}",

    "@keyframes mbk-de{0%{opacity:0}6%{opacity:1}76%{opacity:1;filter:none}82%{opacity:1;filter:brightness(1.6)}100%{opacity:0;filter:brightness(1)}}",
    "@keyframes mbk-sen{0%{opacity:1;transform:scaleX(0)}55%{opacity:1;transform:scaleX(1)}100%{opacity:0;transform:scaleX(1)}}",
    "@keyframes mbk-hiraku{0%{clip-path:inset(50% 0 50% 0)}100%{clip-path:inset(0 0 0 0)}}",
    "@keyframes mbk-hirogaru{0%{letter-spacing:.1em;padding-left:.1em;opacity:.3}100%{letter-spacing:.6em;padding-left:.6em;opacity:1}}",
    "@keyframes mbk-gauge{0%{width:0}100%{width:100%}}",
    "@keyframes mbk-obi-de{0%{opacity:0;transform:scaleY(0)}100%{opacity:.5;transform:scaleY(1)}}",
    "@keyframes mbk-obi-de2{0%{opacity:0;transform:scaleY(0)}100%{opacity:.9;transform:scaleY(1)}}",
    "@keyframes mbk-nagare{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}",
    "@keyframes mbk-tenmetsu{0%{opacity:1}50%{opacity:0}}",
    "@keyframes mbk-wa{0%{transform:scale(.15) rotate(-40deg);opacity:0}30%{opacity:1}100%{transform:scale(1) rotate(0);opacity:.85}}",
    "@media (prefers-reduced-motion:reduce){" + P + "," + P + " *{animation:none !important}}"
  ].join("\n");

  function mk(tag, cls, text) { var e = D.createElement(tag); if (cls) e.className = cls; if (text) e.textContent = text; return e; }
  function rgb(hex) {
    var m = /^#?([0-9a-f]{6})$/i.exec(String(hex || "").trim());
    var n = parseInt(m ? m[1] : "8FD8FF", 16);
    return (n >> 16 & 255) + "," + (n >> 8 & 255) + "," + (n & 255);
  }

  // 一字ずつ走る：決まった字＋ちらつく1字＋まだの字（場所は取っておく＝窓の大きさが揺れない）
  function hashiruAte(el, text, ban) {
    el.textContent = "";
    var a = mk("span"), b = mk("span"), c = mk("span", "mbk-mada", text);
    el.appendChild(a); el.appendChild(b); el.appendChild(c);
    hashiri.push({ text: text, a: a, b: b, c: c, t: ban[0], d: ban[1], n: -1 });
  }
  function ima() { return W.performance && performance.now ? performance.now() : Date.now(); }
  function koma() {
    var t = ima() - t0, i, h, n;   // 描く時の時刻で決める（描き直しが遅れても、字はその時刻の所まで出る）
    for (i = 0; i < hashiri.length; i++) {
      h = hashiri[i];
      n = t < h.t ? 0 : Math.min(h.text.length, Math.floor((t - h.t) / h.d * h.text.length) + 1);
      if (n === h.n && n >= h.text.length) continue;
      h.n = n;
      var mada = t < h.t;
      h.a.textContent = mada ? "" : h.text.slice(0, Math.max(0, n - 1)) + (n >= h.text.length ? h.text.slice(-1) : "");
      h.b.textContent = mada || n >= h.text.length ? "" : (/\s/.test(h.text.charAt(n - 1)) ? " " : F.chira.charAt(r(F.chira.length)));
      h.c.textContent = mada ? h.text : h.text.slice(Math.max(0, n));
    }
    if (kazu) kazu.textContent = ("00" + Math.min(100, Math.max(0, Math.round((t - 260) / 10)))).slice(-3) + "%";
    if (kei && t < 1300) kei.textContent = F.kei();
    if (t < NAGASA) raf = W.requestAnimationFrame(koma);
  }

  function kesu() {
    if (!root) return;
    W.removeEventListener("pointerdown", kesu, true);
    W.removeEventListener("touchstart", kesu, true);
    W.removeEventListener("keydown", kesu, true);
    if (raf) W.cancelAnimationFrame(raf);
    clearTimeout(owari);
    if (root.parentNode) root.parentNode.removeChild(root);
    root = null; hashiri = []; kazu = kei = null;
  }

  function kimeru(e, f) { return FUUN.hasOwnProperty(e) ? e : FUUN.hasOwnProperty(f) ? f : "kinmirai"; }
  function erabareta() { try { var v = W.localStorage.getItem(KIOKU); return FUUN.hasOwnProperty(v) ? v : ""; } catch (e) { return ""; } }
  function erabu(f) {   // 使う人が選んだ雰囲気を端末に覚える（"" か null で忘れる・知らない名前は何もしない）。出来た時 true
    try { if (FUUN.hasOwnProperty(f)) W.localStorage.setItem(KIOKU, f); else if (!f) W.localStorage.removeItem(KIOKU); else return false; return true; } catch (e) { return false; }
  }

  function dasu(s) {
    if (deta) return false;   // アプリを起こした時の1回だけ
    deta = true;
    s = s || {};
    var fuun = kimeru(erabareta(), s.fuun);   // 使う人が選んだ物が先・無ければ製品の設定・それも無ければ近未来
    F = FUUN[fuun];
    var namae = String(s.namae || ""), yomi = String(s.yomi || ""), sei = String(s.seishiki || "");
    var nanori = String(s.nanori || (namae ? namae + "、起動。" : ""));
    if (!D.body) { D.addEventListener("DOMContentLoaded", function () { deta = false; dasu(s); }); return true; }
    var reduce = !!(W.matchMedia && W.matchMedia("(prefers-reduced-motion: reduce)").matches);
    if (!D.getElementById(ID + "Css")) { var st = mk("style"); st.id = ID + "Css"; st.textContent = CSS; (D.head || D.body).appendChild(st); }
    root = mk("div", "f-" + fuun); root.id = ID; root.setAttribute("aria-hidden", "true");
    root.style.setProperty("--mbk", rgb(s.iro || F.iro));
    root.appendChild(mk("div", "mbk-hikari"));
    root.appendChild(mk("div", "mbk-wa"));
    var ue = mk("div", "mbk-obi mbk-ue"), sh = mk("div", "mbk-obi mbk-shita");
    ue.appendChild(mk("span", "", (F.ue || F.obi)())); sh.appendChild(mk("span", "", F.obi()));
    root.appendChild(ue); root.appendChild(sh);
    var mado = mk("div", "mbk-mado");
    ["mbk-k mbk-k1", "mbk-k mbk-k2", "mbk-k mbk-k3", "mbk-k mbk-k4"].forEach(function (c) { mado.appendChild(mk("i", c)); });
    var hed = mk("div", "mbk-hed"), hl = mk("span"), hr = mk("span", "", F.kei());
    hed.appendChild(hl); hed.appendChild(hr); mado.appendChild(hed); kei = hr;
    var mei = mk("div", "mbk-mei mbk-hikaru"), yo = mk("div", "mbk-yomi mbk-hikaru"), se = mk("div", "mbk-sei"), lab = mk("div", "mbk-lab");
    mado.appendChild(mei); if (yomi) mado.appendChild(yo); if (sei) mado.appendChild(se); mado.appendChild(lab);
    var g = mk("div", "mbk-gauge"); g.appendChild(mk("b")); mado.appendChild(g);
    var s2 = mk("div", "mbk-shita2"), na = mk("div", "mbk-nanori mbk-hikaru"), nat = mk("span"), ka = mk("span", "", "100%");
    na.appendChild(mk("span", "", F.mae)); na.appendChild(nat); na.appendChild(mk("i"));
    s2.appendChild(na); s2.appendChild(ka); mado.appendChild(s2); kazu = ka;
    root.appendChild(mado);
    root.appendChild(mk("div", "mbk-sen"));   // 光の線は窓の外（窓は開くまで切り抜かれていて、中だと見えない）
    var moji = [[hl, F.hed(yomi || namae), BAN.hed], [mei, namae, BAN.mei], [yo, yomi, BAN.yomi], [se, sei, BAN.sei],
                [lab, "MadbroLab", BAN.lab], [nat, nanori, BAN.nanori]];
    moji.forEach(function (m) { if (reduce) m[0].textContent = m[1]; else hashiruAte(m[0], m[1], m[2]); });
    if (reduce) { kazu = kei = null; }
    D.body.appendChild(root);
    W.addEventListener("pointerdown", kesu, true);   // どこかに触れたら消える（消すだけ。触った事は止めない＝下の画面にそのまま届く）
    W.addEventListener("touchstart", kesu, { capture: true, passive: true });
    W.addEventListener("keydown", kesu, true);
    t0 = ima();
    if (!reduce) { koma(); }
    owari = setTimeout(kesu, reduce ? 1200 : NAGASA + 60);   // 画面が裏にいて動きが止まっていても、時間が来たら必ず消す
    return true;
  }

  W.KidouLogo = { v: VER, dasu: dasu, kesu: kesu, nagasa: NAGASA, fuun: Object.keys(FUUN), namae: NAMAE, mirai: MIRAI,
                  erabu: erabu, erabareta: erabareta, kimeru: kimeru, deteiru: function () { return !!root; },
                  jikan: function () { return root ? ima() - t0 : -1; } };   // 出てから何ミリ秒か（試験・写し取り用）
})(window);

/* MadbroLab 起動ロゴの部品 KidouLogo（Web 用・1.2.0・2026-11-26 SE室。ひな型＝言霊 KOTODAMA）
   全社の製品が、この1つを写して使う。ほかの物に寄りかからない（読むだけで動く・見た目も中に入っている・外から何も取り寄せない）。
   形：深い色の地に細い線の窓。「ウェーン」と1本の光の線が横に伸び、窓が上下に開く → 文字が一字ずつ走って出る
       （製品の名前と読み＝大／頭文字の正式名＝小／MadbroLab＝さらに小）→ 計器の数字と帯が流れる → 相棒が一言名乗る（文字）→ 消える。
       全部で約1.9秒。押さなくても消える。
   雰囲気（fuun）は増やせる（1.2.0・今は5つ）。下の表 FUUN に1項目足すだけで、選ぶ所にも自動で並ぶ。動きの順・秒数・3段の並びは全部同じ：
     kinmirai  ＝近未来（既定）。少し先の未来の機械の起動画面。青白い光。
     ken_mahou ＝剣と魔法の世界の相棒の案内の窓。金の細い二重線・星の印・光の輪。
     koutetsu  ＝鋼鉄の機械・システム。鉄の板の地・太い枠と鋲・区切りの計器・機械仕掛けの開き方。
     kodai_tou ＝古代の塔。石の地・金の光。石の段が下から積み上がり、積んだ縁が光り、最後に塔の頂が光る。
     sawayaka  ＝さわやか。白い地・藍の字・細い線1本。頭文字が縦に並び、右の言葉が1つずつ灯る（kotoba）。
   守る事：アプリを起こした時の1回だけ（同じページで2回呼んでも1回）／指は全部すり抜けて下の画面（録音の丸など）に届く／
          どこかに触れた・キーを押したら、その場で消える／音は出さない／絵は使わない（文字と線と光だけ）／端末に元からある書体だけ。
   呼び方（製品ごとに変えるのは、名前・読み・正式名・名乗り・色1つ。雰囲気は fuun の1語）：
     KidouLogo.dasu({namae:"言霊", yomi:"KOTODAMA",
                     seishiki:"Keyword-Oriented Transcription & Output Document Automated Management Archive",
                     nanori:"言霊、起動。", fuun:"kinmirai", iro:"#8FD8FF",
                     kotoba:["Keyword","Oriented","Transcription","Output","Document","Automated","Management","Archive"]});
   nanori を省くと「<namae>、起動。」。fuun を省くと kinmirai。iro を省くと雰囲気ごとの色（表の iro）。
   kotoba＝頭文字の名前の、頭文字ごとの言葉（さわやかが使う。省いてよい＝さわやかは名前を1行で出す）。
   使う人が選ぶ口（1.1.0）：KidouLogo.erabu("ken_mahou") でその端末に覚える（localStorage madbro_kidou_fuun）。覚えた物は fuun の設定より先。
     KidouLogo.erabu("") で忘れる＝製品の設定に戻る。KidouLogo.erabareta() は覚えた物（無ければ ""）。
     選ぶ所は KidouLogo.fuun（表の並び）と KidouLogo.namae[f]（出す名前）から作る＝表に足せば自動で増える。
   近未来の上の帯は、会社がこの先も動き続けている事を伝える一言 MIRAI をゆっくり流す（全社で同じ字）。 */
(function (W) {
  "use strict";
  if (W.KidouLogo) return;
  var D = W.document, VER = "1.2.0", ID = "mbkKidou", KIOKU = "madbro_kidou_fuun";
  var MIRAI = "次の時代へ同期中 ─ CONTINUING";   // 近未来の上の帯の一言（Android の MIRAI と同じ字）
  var NAGASA = 1900;                       // 全部の長さ（ミリ秒）。動きの秒数は全部ここと下の表だけ
  var BAN = {   // 一字ずつ走る所：[始まり, 長さ]（ミリ秒）
    mei: [300, 260], yomi: [380, 380], sei: [480, 520], lab: [700, 260], nanori: [1060, 300], hed: [140, 220]
  };
  var TOU = [60, 85, 200, 10], TOU_HIKARI = [1030, 300];   // 古代の塔：[1段目の始まり, 段ごとのずれ, 1段の長さ, 段の数]・頂の光 [始まり, 長さ]
  var SAWA = [300, 700, 200, 100, 400];   // さわやか：[言葉が灯る始まり, 最後の言葉までの幅, 1つが灯る長さ, 線の始まり, 線が伸びる長さ]
  function r(n) { return Math.floor(Math.random() * n); }
  function hex4() { return "0x" + ("000" + r(65536).toString(16).toUpperCase()).slice(-4); }
  function nagare(f, n) { var s = [], i; for (i = 0; i < (n || 18); i++) s.push(f(i)); s = s.join("") ; return s + s; }   // 2つ並べて半分ずらすと、切れ目なく流れる
  function roma() { return ["I", "II", "III", "IV", "V", "VI", "VII", "IX", "XII"][r(9)]; }
  var P = "#" + ID, MONO = "ui-monospace,'SF Mono',Menlo,Consolas,'Roboto Mono',monospace";
  var MIN = "'Hiragino Mincho ProN','Yu Mincho','YuMincho','Noto Serif JP','Noto Serif CJK JP',serif";
  var SERIF = "'Iowan Old Style','Palatino Linotype','Book Antiqua',Palatino,Georgia," + MIN;
  // 金の窓の形（剣と魔法・古代の塔が使う）：明朝と飾りのある洋字・金の細い線と四隅の印 c・二重の下線
  function kinCss(S, c) {
    return [S + "{font-family:" + SERIF + "}",
      S + " .mbk-obi{font-family:inherit;font-size:9.5px;letter-spacing:.18em;border-color:rgba(var(--mbk),.3);opacity:.45}",
      S + " .mbk-k{border:0;width:auto;height:auto;font:13px/1 serif;color:rgba(var(--mbk),1);text-shadow:0 0 8px rgba(var(--mbk),.9)}",
      S + " .mbk-k::before{content:'" + c + "'}",
      S + " .mbk-k1{left:-7px;top:-8px}" + S + " .mbk-k2{right:-7px;top:-8px}" + S + " .mbk-k3{left:-7px;bottom:-8px}" + S + " .mbk-k4{right:-7px;bottom:-8px}",
      S + " .mbk-hed{font-family:inherit;font-size:10px;letter-spacing:.16em;border-bottom-style:double;border-bottom-width:3px;border-color:rgba(var(--mbk),.3)}",
      S + " .mbk-yomi{font-family:inherit;font-weight:700}" + S + " .mbk-sei{font-style:italic;color:inherit;opacity:.8}",
      S + " .mbk-lab{font-family:inherit;font-size:8.5px}" + S + " .mbk-gauge{height:1px}" + S + " .mbk-shita2{font-family:inherit;font-size:10px}",
      S + " .mbk-nanori{color:inherit;font-family:" + MIN + "}" + S + " .mbk-nanori i{width:2px}"];
  }

  // ==== 雰囲気の表（1.2.0）：1つ足す＝ここに1項目足すだけ。選ぶ所（KidouLogo.fuun・namae）に自動で並ぶ ====
  // namae＝選ぶ所に出す名前／iro＝色1つ／mae＝名乗りの頭の印／chira＝一字ずつ走る時にちらつく字／hed・kei・obi・ue＝窓の上の段・数・帯の字
  // css(S)＝見た目（S＝この雰囲気の時のロゴの外枠の名前）／kazari(root)＝飾り（無くてよい）。Android（KidouLogo.java の KATA）にも同じ名前・色で1項目足す
  var FUUN = {
    kinmirai: { namae: "近未来", iro: "#8FD8FF", mae: "» ", chira: "アイウエオカキクケコサシスセソ0123456789ABCDEF#%&*+=<>/",
      hed: function (y) { return "SYS.BOOT // " + y; },
      kei: function () { return hex4() + " / " + hex4(); },
      obi: function () { return nagare(function (i) { return (i % 3 === 0 ? hex4() : i % 3 === 1 ? (Math.random() * 100).toFixed(2) : "CH" + ("0" + (i % 12 + 1)).slice(-2) + " SYNC") + "  │  "; }); },
      ue: function () { return nagare(function () { return MIRAI + "  │  " + hex4() + "  │  "; }, 6); },   // 上の帯＝会社がこの先も続いていく一言
      // 上の帯（MIRAI）：読めるように明るく・少し大きく・ゆっくり流す
      css: function (S) { return [S + " .mbk-ue{font-size:10.5px;color:rgba(var(--mbk),1);animation-name:mbk-obi-de2}" + S + " .mbk-ue span{animation-duration:9000ms}"]; } },
    // 剣と魔法の世界の相棒：深い藍の地・金の細い二重線・星の印・広がる光の輪
    ken_mahou: { namae: "剣と魔法の相棒", iro: "#E8C77A", mae: "◆ ", chira: "✦✧·*+◇◆†‡§",
      hed: function (y) { return "✧ 相棒の窓 ─ " + y; },
      kei: function () { return "MP " + (100 + r(900)) + " / 999"; },
      obi: function () { var w = ["INVOCATIO", "VERBUM", "ANIMA", "LUX", "FIDES", "MEMORIA", "VOX", "SAPIENTIA"];
        return nagare(function (i) { return (i % 2 ? w[r(w.length)] : roma()) + "  ✦  "; }); },
      kazari: function (root) { root.appendChild(mk("div", "mbk-wa")); },
      css: function (S) { return kinCss(S, "\\2726").concat([S + "{background:#0B0816;color:#FBF3DF}",
        S + " .mbk-hikari{background:radial-gradient(55% 40% at 50% 50%,rgba(var(--mbk),.14),transparent 72%),radial-gradient(circle at 50% 50%,rgba(70,40,120,.35),transparent 75%)}",
        S + " .mbk-wa{position:absolute;left:50%;top:50%;width:min(130vw,600px);aspect-ratio:1;margin-left:calc(min(130vw,600px) / -2);",
        "  margin-top:calc(min(130vw,600px) / -2);border-radius:50%;border:1px solid rgba(var(--mbk),.35);",
        "  box-shadow:0 0 0 6px rgba(var(--mbk),.04),0 0 0 7px rgba(var(--mbk),.22),inset 0 0 30px rgba(var(--mbk),.12);animation:mbk-wa 1500ms 60ms cubic-bezier(.2,.8,.2,1) both}",
        S + " .mbk-mado{border-color:rgba(var(--mbk),.6);background:linear-gradient(rgba(30,20,50,.75),rgba(15,10,30,.75));",
        "  box-shadow:0 0 0 4px #0B0816,0 0 0 5px rgba(var(--mbk),.35),0 0 30px rgba(var(--mbk),.15)}",
        "@keyframes mbk-wa{0%{transform:scale(.15) rotate(-40deg);opacity:0}30%{opacity:1}100%{transform:scale(1) rotate(0);opacity:.85}}"]); } },
    // 鋼鉄の機械：鉄の板の地（細い縦の筋）・太い二重の枠と鋲・区切りの計器・機械仕掛けにカクカク開く
    koutetsu: { namae: "鋼鉄の機械", iro: "#F2A93B", mae: "> ", chira: "0123456789#=/|-+",
      hed: function (y) { return "MACHINE " + y + " ─ SELF CHECK"; },
      kei: function () { return "PSI " + (120 + Math.random() * 20).toFixed(1) + " / " + (23.5 + Math.random()).toFixed(1) + "V"; },
      obi: function () { return nagare(function (i) { return ["PRESS " + (100 + Math.random() * 3).toFixed(1) + "kPa", "TEMP " + (35 + Math.random() * 3).toFixed(1) + "°C",
        "RPM " + (1100 + r(300)), "VOLT " + (23.5 + Math.random()).toFixed(1) + "V", "TORQ " + (80 + r(20)) + "%"][i % 5] + "  ┃  "; }); },
      css: function (S) { return [S + "{background:linear-gradient(#1B1E21,#0C0E10);color:#DDE2E7}",
        S + " .mbk-hikari{background:repeating-linear-gradient(90deg,rgba(255,255,255,.022) 0 1px,transparent 1px 4px),radial-gradient(60% 45% at 50% 50%,rgba(var(--mbk),.08),transparent 70%)}",
        S + " .mbk-obi{height:18px;line-height:18px;font-weight:700;color:rgba(200,206,212,.75);border-width:2px;border-color:rgba(160,168,176,.3);background:rgba(0,0,0,.25)}",
        S + " .mbk-mado{border:2px solid rgba(176,184,192,.6);background:linear-gradient(#272B2F,#191C1F);",
        "  box-shadow:inset 0 0 0 4px #1D2024,inset 0 0 0 5px rgba(176,184,192,.22),0 6px 24px rgba(0,0,0,.6);animation:mbk-hiraku 320ms 200ms steps(6,end) both}",
        S + " .mbk-sen{height:3px;box-shadow:0 0 6px rgba(var(--mbk),.8)}",
        S + " .mbk-k{border:0;width:auto;height:auto;font:7px/1 sans-serif;color:rgba(150,158,166,.9)}" + S + " .mbk-k::before{content:'\\25CF'}",
        S + " .mbk-k1{left:6px;top:6px}" + S + " .mbk-k2{right:6px;top:6px}" + S + " .mbk-k3{left:6px;bottom:6px}" + S + " .mbk-k4{right:6px;bottom:6px}",
        S + " .mbk-hed{font-weight:700;color:rgba(var(--mbk),.95);border-bottom:2px solid rgba(176,184,192,.25);margin:0 6px}",
        S + " .mbk-hikaru{text-shadow:0 1px 0 #000,0 -1px 0 rgba(255,255,255,.12)}",
        S + " .mbk-mei{font-family:'Hiragino Sans','Yu Gothic','Noto Sans JP','Noto Sans CJK JP',sans-serif;font-weight:900;color:#E4E8EC}",
        S + " .mbk-yomi{font-family:" + MONO + ";font-weight:800;color:rgba(var(--mbk),1);text-shadow:0 0 6px rgba(var(--mbk),.5)}",
        S + " .mbk-sei{font-family:" + MONO + ";font-size:clamp(8px,2.3vw,9.5px);text-transform:uppercase;color:rgba(200,206,212,.7)}",
        S + " .mbk-lab{font-family:" + MONO + ";font-weight:700;color:rgba(200,206,212,.6)}",
        S + " .mbk-gauge{height:7px;margin:12px 6px 7px;background:rgba(0,0,0,.45);box-shadow:inset 0 0 0 1px rgba(176,184,192,.25)}",
        S + " .mbk-gauge b{top:1px;bottom:1px;left:1px;box-shadow:none;background:repeating-linear-gradient(90deg,rgba(var(--mbk),1) 0 9px,transparent 9px 11px);animation-timing-function:steps(12,end)}",
        S + " .mbk-shita2{font-weight:700;margin:0 6px}" + S + " .mbk-nanori{font-weight:700;color:rgba(var(--mbk),1);text-shadow:0 0 6px rgba(var(--mbk),.6)}"]; } },
    // 古代の塔（2026-11-26 リバベル主任の頼み・全社で使える1つ）：石の地・金の光。石の段が下から1段ずつ積み上がり、積んだ縁が光って落ち着き、最後に頂が光る
    kodai_tou: { namae: "古代の塔", iro: "#F2C25C", mae: "▲ ", chira: "▲△◇□■ΛΔΣΩ·",
      hed: function (y) { return "▲ いにしえの塔 ─ " + y; },
      kei: function () { return "STRATUM " + ("0" + (1 + r(12))).slice(-2) + " / 12"; },
      obi: function () { var w = ["LAPIS", "TURRIS", "LINGUA", "VERBUM", "UNITAS", "ΛΟΓΟΣ", "ΠΥΡΓΟΣ", "ΓΛΩΣΣΑ"];
        return nagare(function (i) { return (i % 2 ? w[r(w.length)] : roma()) + "  ▲  "; }); },
      kazari: function (root) {
        var t = mk("div", "mbk-tou"), i, b;
        for (i = 0; i < TOU[3]; i++) {   // 下の段ほど広く、上ほど細い。段ごとに石の継ぎ目を半分ずらす
          b = mk("b"); b.style.bottom = "calc(8vh + " + (i * 6.8) + "vh)"; b.style.width = "calc(min(82vw,430px) * " + (1 - i * 0.075).toFixed(3) + ")";
          b.style.animationDelay = (TOU[0] + i * TOU[1]) + "ms"; if (i % 2) b.style.backgroundPosition = "18px 0"; t.appendChild(b);
        }
        t.appendChild(mk("i")); root.appendChild(t);
      },
      css: function (S) { return kinCss(S, "\\25C6").concat([S + "{background:linear-gradient(#2B251D,#0F0D0A);color:#F7EDD5}",
        S + " .mbk-hikari{background:radial-gradient(55% 40% at 50% 50%,rgba(var(--mbk),.14),transparent 72%),radial-gradient(circle at 50% 70%,rgba(120,90,40,.3),transparent 75%),",
        "  repeating-linear-gradient(0deg,rgba(255,255,255,.025) 0 1px,transparent 1px 22px)}",
        S + " .mbk-mado{border-color:rgba(var(--mbk),.6);background:linear-gradient(rgba(43,36,27,.82),rgba(20,17,13,.82));",
        "  box-shadow:0 0 0 4px #15120E,0 0 0 5px rgba(var(--mbk),.35),0 0 30px rgba(var(--mbk),.15)}",
        S + " .mbk-tou{position:absolute;inset:0}",
        S + " .mbk-tou b{position:absolute;left:50%;height:6.8vh;transform:translateX(-50%);border-top:1px solid rgba(var(--mbk),.35);",
        "  background:repeating-linear-gradient(90deg,transparent 0 34px,rgba(0,0,0,.45) 34px 36px),#3A3226;animation:mbk-tou " + (TOU[2] + 400) + "ms linear both}",
        S + " .mbk-tou i{position:absolute;left:50%;top:calc(92vh - " + (TOU[3] * 6.8) + "vh);width:min(60vw,300px);aspect-ratio:1;transform:translate(-50%,-50%);border-radius:50%;",
        "  background:radial-gradient(rgba(var(--mbk),.55),transparent 65%);animation:mbk-tou-i " + TOU_HIKARI[1] + "ms " + TOU_HIKARI[0] + "ms ease-out both}",
        "@keyframes mbk-tou{0%{opacity:0;transform:translate(-50%,60%)}" + (TOU[2] / (TOU[2] + 400) * 100).toFixed(1) + "%{opacity:1;transform:translate(-50%,0);border-top-color:rgba(var(--mbk),1);box-shadow:0 -1px 8px rgba(var(--mbk),.8)}",
        "  100%{opacity:1;transform:translate(-50%,0)}}",
        "@keyframes mbk-tou-i{0%{opacity:0;transform:translate(-50%,-50%) scale(.4)}100%{opacity:1;transform:translate(-50%,-50%) scale(1)}}"]); } },
    // さわやか（2026-11-26 社長「もっとさわやかで　シンプルなほうが俺好み」）：白い地・藍の字・細い線1本。窓は使わない（kata＝自分の並び）。
    // 頭文字の名前（例 E.N.I.S.H.I）は dasu の kotoba に頭文字ごとの言葉を並べる → 頭文字が縦に大きく並び、右の言葉が1つずつ灯る。kotoba が無ければ名前を静かに1行
    sawayaka: { namae: "さわやか", iro: "#2B4C8C", mae: "", chira: "·",
      kata: function (root, o) {
        var w = mk("div", "mbk-sw"), n = o.kotoba.length, z, i, p, sp;
        if (n > 1) {
          z = Math.min(44, (W.innerHeight || 640) * 0.6 / n, (W.innerWidth || 360) * 0.11);
          w.style.setProperty("--z", z.toFixed(1) + "px");
          for (i = 0; i < n; i++) {
            p = mk("p"); p.appendChild(mk("b", "", o.kotoba[i].charAt(0)));
            sp = mk("span", "", o.kotoba[i].slice(1)); sp.style.animationDelay = (SAWA[0] + Math.round(i * SAWA[1] / (n - 1))) + "ms";
            p.appendChild(sp); w.appendChild(p);
          }
        } else { p = mk("div", "mbk-sw-ichi", o.namae); if (o.yomi) p.appendChild(mk("small", "", o.yomi)); w.appendChild(p); }
        w.appendChild(mk("div", "mbk-sw-sen"));
        var sh = mk("div", "mbk-sw-shita"), na = mk("span");
        sh.appendChild(na); sh.appendChild(mk("span", "", "MadbroLab")); w.appendChild(sh);
        o.hashiru(na, o.nanori, BAN.nanori);
        root.appendChild(w);
      },
      css: function (S) { return [S + "{background:#F7F9FC;color:#1F3A6E;animation-name:mbk-de2;font-family:'Helvetica Neue','Segoe UI',system-ui,sans-serif}",
        S + " .mbk-sw{display:flex;flex-direction:column;align-items:flex-start;min-width:min(80vw,320px)}",
        S + " .mbk-sw p{display:flex;align-items:baseline;line-height:1.08;white-space:nowrap}",
        S + " .mbk-sw b{width:1.05em;font-size:var(--z);font-weight:600;color:rgba(var(--mbk),1);animation:mbk-sw-b 300ms 80ms ease-out both}",
        S + " .mbk-sw p span{display:inline-block;font-size:calc(var(--z) * .42);font-weight:300;letter-spacing:.06em;animation:mbk-sw-w " + SAWA[2] + "ms ease-out both}",
        S + " .mbk-sw-ichi{font-size:26px;font-weight:500;letter-spacing:.14em;animation:mbk-sw-b 300ms 80ms ease-out both}" + S + " .mbk-sw-ichi small{font-size:11px;letter-spacing:.4em;margin-left:14px;opacity:.7}",
        S + " .mbk-sw-sen{align-self:stretch;height:1px;margin:14px 0 8px;background:rgba(var(--mbk),.7);transform-origin:left;animation:mbk-sw-sen " + SAWA[4] + "ms " + SAWA[3] + "ms ease-out both}",
        S + " .mbk-sw-shita{align-self:stretch;display:flex;justify-content:space-between;gap:16px;font-size:11px;letter-spacing:.14em;color:rgba(31,58,110,.75)}",
        "@keyframes mbk-de2{0%{opacity:0}6%{opacity:1}82%{opacity:1}100%{opacity:0}}@keyframes mbk-sw-b{0%{opacity:0}100%{opacity:1}}",
        "@keyframes mbk-sw-w{0%{opacity:0;transform:translateX(-6px)}100%{opacity:1;transform:none}}@keyframes mbk-sw-sen{0%{transform:scaleX(0)}100%{transform:scaleX(1)}}"]; } }
  };
  var NAMAE = {};
  Object.keys(FUUN).forEach(function (f) { NAMAE[f] = FUUN[f].namae; });   // 選ぶ所に出す名前（表から作る）
  var deta = false, root = null, raf = 0, owari = 0, t0 = 0, hashiri = [], kazu = null, kei = null, F = FUUN.kinmirai;
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
    "@keyframes mbk-de{0%{opacity:0}6%{opacity:1}76%{opacity:1;filter:none}82%{opacity:1;filter:brightness(1.6)}100%{opacity:0;filter:brightness(1)}}",
    "@keyframes mbk-sen{0%{opacity:1;transform:scaleX(0)}55%{opacity:1;transform:scaleX(1)}100%{opacity:0;transform:scaleX(1)}}",
    "@keyframes mbk-hiraku{0%{clip-path:inset(50% 0 50% 0)}100%{clip-path:inset(0 0 0 0)}}",
    "@keyframes mbk-hirogaru{0%{letter-spacing:.1em;padding-left:.1em;opacity:.3}100%{letter-spacing:.6em;padding-left:.6em;opacity:1}}",
    "@keyframes mbk-gauge{0%{width:0}100%{width:100%}}",
    "@keyframes mbk-obi-de{0%{opacity:0;transform:scaleY(0)}100%{opacity:.5;transform:scaleY(1)}}",
    "@keyframes mbk-obi-de2{0%{opacity:0;transform:scaleY(0)}100%{opacity:.9;transform:scaleY(1)}}",
    "@keyframes mbk-nagare{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}",
    "@keyframes mbk-tenmetsu{0%{opacity:1}50%{opacity:0}}",
    "@media (prefers-reduced-motion:reduce){" + P + "," + P + " *{animation:none !important}}"
  ].concat(Object.keys(FUUN).map(function (f) { return FUUN[f].css(P + ".f-" + f).join("\n"); })).join("\n");   // 雰囲気ごとの見た目（表から）

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
    function hashiru(el, text, ban) { if (reduce) el.textContent = text; else hashiruAte(el, text, ban); }
    if (F.kata) {   // 自分の並びを持つ雰囲気（さわやか）：窓・帯・計器は使わない
      F.kata(root, { namae: namae, yomi: yomi, nanori: nanori, hashiru: hashiru,
        kotoba: (s.kotoba && s.kotoba.length ? s.kotoba : []).map(String).filter(function (k) { return k.trim(); }) });
      kazu = kei = null;
    } else {
    root.appendChild(mk("div", "mbk-hikari"));
    if (F.kazari) F.kazari(root);
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
    moji.forEach(function (m) { hashiru(m[0], m[1], m[2]); });
    if (reduce) { kazu = kei = null; }
    }
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

// 入口アプリ（ページ版）。iPhone では、これ自体が入口になる（ホーム画面に置いて使う）。
// Windows・Android では、入口アプリ本体を入れる案内と、招待（初めの設定）を本体へ渡すボタンを出す。
// 招待＝ URL の #i=<base64url の JSON>。# の後ろはサーバーへ送られない。受け取ったらこの機械の中にだけしまう。
(function () {
  "use strict";
  var KAGI = "iriguchi_settei";          // しまう場所の名前（localStorage と cookie）
  var BAN = "0.1.0";
  var $ = function (id) { return document.getElementById(id); };

  // ── 機械を見分ける ──
  function kikai() {
    var ua = navigator.userAgent || "";
    if (/iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) return "iphone";
    if (/Android/.test(ua)) return "android";
    if (/Windows/.test(ua)) return "windows";
    return "iphone";   // その他の機械は、ページだけで使える形（iPhone と同じ）にする
  }
  var KIKAI = (location.search.match(/[?&]kikai=(\w+)/) || [])[1] || kikai();
  var HOME = (window.navigator.standalone === true) || (window.matchMedia && matchMedia("(display-mode: standalone)").matches);

  // ── 招待を読む・しまう ──
  function b64Yomu(s) {
    var at = s.search(/(^|[#?&:\/])i=/);
    if (at < 0) return null;
    var b = s.slice(s.indexOf("i=", at) + 2).split(/[&\s"]/)[0];
    try {
      b = decodeURIComponent(b).replace(/-/g, "+").replace(/_/g, "/");
      while (b.length % 4) b += "=";
      var bin = atob(b), u = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
      var d = JSON.parse(new TextDecoder("utf-8").decode(u));
      return d && d.v === 1 ? { d: d, b: s.slice(s.indexOf("i=", at) + 2).split(/[&\s"]/)[0] } : null;
    } catch (e) { return null; }
  }
  function shimau(b) {
    try { localStorage.setItem(KAGI, b); } catch (e) {}
    // ホーム画面のアプリへ持ち越すため cookie にも置く（400日）
    document.cookie = KAGI + "=" + b + "; Max-Age=34560000; Path=/; SameSite=Lax" + (location.protocol === "https:" ? "; Secure" : "");
  }
  function dasu() {
    var b = null;
    try { b = localStorage.getItem(KAGI); } catch (e) {}
    if (!b) {
      var m = document.cookie.match(new RegExp("(?:^|; )" + KAGI + "=([^;]+)"));
      if (m) b = m[1];
    }
    var r = b ? b64Yomu("i=" + b) : null;
    if (r) shimau(r.b);   // 片方にしか無ければ両方へ戻す
    return r;
  }
  function uketoru(s) {
    var r = b64Yomu(s || "");
    if (!r) return false;
    shimau(r.b);
    SETTEI = r;
    return true;
  }

  var SETTEI = null;
  (function () {
    var h = location.hash || "";
    if (uketoru(h)) {
      // iPhone では、ホーム画面に置く時に今の住所が使われるので # を残す。他の機械では消す（見えない所へ）。
      if (KIKAI !== "iphone" && history.replaceState) history.replaceState(null, "", location.pathname + location.search);
    } else {
      SETTEI = dasu();
    }
  })();

  // ── 一覧表の波かっこを招待の値で埋める（入口アプリ本体と同じ決まり）──
  // 頭に来る {x} はそのまま、途中の {x} は URL 用に包む。{x?} と {d} は無くてもよい。必須の値が無ければ null。
  function umeru(tpl, id) {
    if (!tpl) return null;
    var st = SETTEI ? SETTEI.d : {};
    var sv = (st.soft || {})[id] || {};
    var out = "", i = 0;
    while (i < tpl.length) {
      var a = tpl.indexOf("{", i);
      if (a < 0) { out += tpl.slice(i); break; }
      var z = tpl.indexOf("}", a);
      if (z < 0) { out += tpl.slice(i); break; }
      out += tpl.slice(i, a);
      var key = tpl.slice(a + 1, z), nakutemo = key.slice(-1) === "?";
      if (nakutemo) key = key.slice(0, -1);
      var v = (key === "kaisha" || key === "namae") ? (st[key] || "") : (sv[key] == null ? "" : String(sv[key]));
      if (v === "" && !nakutemo && key !== "d") return null;
      out += a === 0 ? v : encodeURIComponent(v);
      i = z + 1;
    }
    return out;
  }

  // ── 一覧表を読む（電波が無ければ前の写し）──
  var ICHIRAN = null;
  function ichiranYomu() {
    return fetch("ichiran.json?t=" + Date.now(), { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then(function (j) {
      try { localStorage.setItem("iriguchi_ichiran", JSON.stringify(j)); } catch (e) {}
      return j;
    }).catch(function () {
      try { var s = localStorage.getItem("iriguchi_ichiran"); if (s) return JSON.parse(s); } catch (e) {}
      return null;
    });
  }

  // ── 札（ソフト1つ）を作る・変わった所だけ直す ──
  function yousu(g) {
    var w = g[KIKAI === "iphone" ? "iphone" : KIKAI];
    if (!w) return { k: "nai" };
    if (g.jumbi) return { k: "jumbi", moji: "準備中です" + (g.jumbi_wake ? "（" + g.jumbi_wake + "）" : "") };
    if (g.jibun) return { k: "jibun", moji: "このページです" };
    var u = umeru(w.url, g.id);
    if (u == null) return { k: "machi", moji: "会社からの招待がまだです" };
    return { k: "hiraku", moji: "押せば、すぐ使えます", url: u };
  }
  function fudaTsukuru(g) {
    var f = document.createElement("div");
    f.className = "fuda"; f.dataset.key = g.id;
    f.innerHTML = '<div class="shirushi"></div><div class="mannaka"><div class="na"></div><div class="hito"></div>' +
      '<div class="yousu"></div></div><a class="botan" rel="noopener"></a>';
    return f;
  }
  function fudaNaosu(f, g, y) {
    var sh = f.querySelector(".shirushi"), b = f.querySelector(".botan");
    var iro = /^#[0-9a-fA-F]{3,8}$/.test(g.iro || "") ? g.iro : "#708090";
    if (sh.textContent !== g.fuda) sh.textContent = g.fuda;
    if (sh.style.background !== iro) sh.style.background = iro;
    f.querySelector(".na").textContent = g.namae;
    f.querySelector(".hito").textContent = g.hitokoto;
    f.querySelector(".yousu").textContent = y.moji || "";
    if (y.k === "hiraku") {
      b.textContent = "開く"; b.className = "botan"; b.href = y.url; b.removeAttribute("aria-disabled");
      b.onclick = function () {
        try { localStorage.setItem("web_" + g.id, y.url); } catch (e) {}
        if (HOME) { location.href = y.url; return false; }   // ホーム画面のアプリから開く時は同じ窓で
        b.target = "_blank"; return true;
      };
    } else {
      b.textContent = y.k === "jibun" ? "使用中" : (y.k === "jumbi" ? "準備中" : "待ち");
      b.className = "botan dame"; b.removeAttribute("href"); b.setAttribute("aria-disabled", "true"); b.onclick = null;
    }
  }
  function ichiranNaosu() {
    var box = $("ichiran");
    if (!ICHIRAN) { $("ichiran_waku").hidden = true; return; }
    $("ichiran_waku").hidden = !(KIKAI === "iphone");
    var aru = {};
    (ICHIRAN.soft || []).forEach(function (g) {
      try {
        if (!g || !g.id || !g.namae) return;
        var y = yousu(g);
        if (y.k === "nai") return;
        var f = box.querySelector('[data-key="' + g.id + '"]');
        if (!f) f = fudaTsukuru(g);
        fudaNaosu(f, g, y);
        box.appendChild(f);   // 一覧の順に並べ直す（同じ札は動くだけ）
        aru[g.id] = true;
      } catch (e) { /* 1行壊れていても、他の札は出す */ }
    });
    Array.prototype.slice.call(box.children).forEach(function (f) { if (!aru[f.dataset.key]) box.removeChild(f); });
    document.body.dataset.fudaKazu = box.children.length;
  }

  // ── Windows・Android：入口アプリ本体を入れる案内 ──
  function hontaiAnnai() {
    if (KIKAI === "iphone") return;
    var g = ICHIRAN && (ICHIRAN.soft || []).filter(function (x) { return x.jibun; })[0];
    var w = g && g[KIKAI];
    var ol = $("ireru_junban");
    ol.textContent = "";
    var li = function (html) { var e = document.createElement("li"); e.innerHTML = html; ol.appendChild(e); return e; };
    $("ireru_annai").hidden = false;
    if (!w || !w.url) { li("ただいま準備中です。少し待ってから開き直してください。"); return; }
    var mono = new URL(w.url, location.href).href;
    if (KIKAI === "android") {
      li('下のボタンで入口アプリを取ります。<a id="tori" class="botan ookii" href="' + mono + '">入口アプリを取る</a>');
      li("取れたら、画面の上か下に出るお知らせの <b>「開く」</b> を押し、<b>「インストール」</b> を押します。"
        + "「この提供元のアプリを許可」と出たら、オンにして戻ってください。");
      if (SETTEI) {
        var lk = "intent://settei?i=" + SETTEI.b + "#Intent;scheme=madbro-iriguchi;package=jp.madbrolab.iriguchi;"
          + "S.browser_fallback_url=" + encodeURIComponent(mono) + ";end";
        li('入れ終わったら、ここへ戻って押します。<a id="watasu" class="botan ookii" href="' + lk + '">入口アプリに設定を渡す</a>');
      }
    } else {
      li('下のボタンで入口アプリを取ります。<a id="tori" class="botan ookii" href="' + mono + '" download>入口アプリを取る</a>');
      li("取れたら、開きます。青い画面（「WindowsによってPCが保護されました」）が出たら、<b>「詳細情報」</b> → <b>「実行」</b> を押します。");
      if (SETTEI) {
        li('入れ終わったら、ここへ戻って押します。<a id="watasu" class="botan ookii" href="madbro-iriguchi:settei?i=' + SETTEI.b + '">入口アプリに設定を渡す</a>');
      }
    }
    // どちらの機械でも、押した時に招待を写しておく（本体が開いた時に写しから受け取る）
    Array.prototype.forEach.call(ol.querySelectorAll("a"), function (a) {
      a.addEventListener("click", function () { if (SETTEI) utsusu(location.origin + location.pathname + "#i=" + SETTEI.b); });
    });
  }
  function utsusu(s) { try { navigator.clipboard && navigator.clipboard.writeText(s).catch(function () {}); } catch (e) {} }

  // ── お知らせ ──
  function oshirase() {
    var o = $("oshirase");
    if (SETTEI) {
      var d = SETTEI.d;
      o.className = "oshirase yoi";
      o.textContent = (d.kaisha ? d.kaisha + "の " : "") + (d.namae ? d.namae + " 様、" : "") + "招待を受け取りました。";
    } else {
      o.className = "oshirase";
      o.textContent = "会社からの招待がまだ届いていません。届いたリンクから開いてください。";
    }
    o.hidden = false;
    $("harituke").hidden = !(KIKAI === "iphone" && !SETTEI);
    $("home_annai").hidden = !(KIKAI === "iphone" && !HOME);
  }

  function zenbu() { oshirase(); hontaiAnnai(); ichiranNaosu(); }
  function yomiNaoshi() { return ichiranYomu().then(function (j) { ICHIRAN = j; zenbu(); document.body.dataset.yometa = "1"; }); }

  // 貼り付けで受け取る
  $("harituke_osu").addEventListener("click", function () {
    if (!navigator.clipboard || !navigator.clipboard.readText) { $("harituke").querySelector("details").open = true; return; }
    navigator.clipboard.readText().then(function (s) {
      if (uketoru(s)) zenbu(); else $("oshirase").textContent = "コピーした中に、招待が見つかりませんでした。";
    }).catch(function () { $("harituke").querySelector("details").open = true; });
  });
  $("harituke_kakutei").addEventListener("click", function () {
    if (uketoru($("harituke_ran").value)) zenbu(); else $("oshirase").textContent = "招待が読めませんでした。もう一度コピーしてください。";
  });
  $("yomi_naosu").addEventListener("click", yomiNaoshi);
  window.addEventListener("hashchange", function () { if (uketoru(location.hash)) zenbu(); });
  document.addEventListener("visibilitychange", function () { if (!document.hidden) yomiNaoshi(); });

  $("ban").textContent = "版 " + BAN;
  document.body.dataset.kikai = KIKAI;
  window.IRIGUCHI = { umeru: umeru, yomiNaoshi: yomiNaoshi, settei: function () { return SETTEI && SETTEI.d; } };
  yomiNaoshi();

  if ("serviceWorker" in navigator && location.protocol === "https:") navigator.serviceWorker.register("sw.js").catch(function () {});
})();

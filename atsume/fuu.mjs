// KAI社員ページ 封をする係：data.json を社員の合言葉で開く錠にかけて shain/data.enc.json にする。
// 使い方: node fuu.mjs <社長の版 data.json> <社員の版 data_shain.json> <合言葉.json> <出す場所/data.enc.json>
// 合言葉.json の人に "kubun":"shachou" があれば社長の版、無ければ社員の版の鍵を渡す（2026-11-25 箱を2つに）。
// 罠メモ: 中身の鍵 K は毎回作り直す（社員を外したら、その人の合言葉では次から開かない）。
//         合言葉.json は内緒の場所だけに置く。ここに書くのは錠をかけた字の固まりだけ。
import { readFileSync, writeFileSync } from "node:fs";
import { webcrypto as c } from "node:crypto";
const [, , dataP, shainP, aikP, outP] = process.argv;
const ITER = 250000;
const enc = new TextEncoder();
const b64 = (u) => Buffer.from(u).toString("base64");
const rnd = (n) => c.getRandomValues(new Uint8Array(n));
const shain = JSON.parse(readFileSync(aikP, "utf8")).shain;
const hako = [], kagi = {};
for (const [na, p] of [["shachou", dataP], ["shain", shainP]]) {
  const K = await c.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt"]);
  kagi[na] = new Uint8Array(await c.subtle.exportKey("raw", K));
  const iv = rnd(12);
  hako.push({ iv: b64(iv), ct: b64(new Uint8Array(await c.subtle.encrypt({ name: "AES-GCM", iv }, K, readFileSync(p)))) });
}
const wraps = [];
for (const s of shain) {
  const salt = rnd(16), wiv = rnd(12);
  const base = await c.subtle.importKey("raw", enc.encode(s.aikotoba.normalize("NFKC").trim()), "PBKDF2", false, ["deriveKey"]);
  const W = await c.subtle.deriveKey({ name: "PBKDF2", salt, iterations: ITER, hash: "SHA-256" }, base, { name: "AES-GCM", length: 256 }, false, ["encrypt"]);
  wraps.push({ salt: b64(salt), iv: b64(wiv), k: b64(new Uint8Array(await c.subtle.encrypt({ name: "AES-GCM", iv: wiv }, W, kagi[s.kubun === "shachou" ? "shachou" : "shain"]))) });
}
// 誰の錠かは書かない（並びも毎回まぜる）
wraps.sort(() => Math.random() - 0.5);
// 箱の並びもまぜる（どちらが社長の箱かは開けた人にしか分からない）
hako.sort(() => Math.random() - 0.5);
writeFileSync(outP, JSON.stringify({ v: 2, iter: ITER, wraps, hako }));
console.log(`OK 錠 ${wraps.length} 人分・箱 ${hako.length}`);

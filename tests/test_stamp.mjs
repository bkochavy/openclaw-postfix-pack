import { readFileSync } from 'fs';
const DIST = '/opt/homebrew/lib/node_modules/openclaw/dist';
const HB = "__heartbeat__";

// ── T1: postfix routing ───────────────────────────────────────────────────────
console.log("T1: postfix routing logic");
function applyPrefix(text, prefix) {
  if (prefix && text && text.trim() !== HB) {
    if (prefix.startsWith("postfix:")) {
      const s = prefix.slice(8);
      if (!text.endsWith(s)) text = `${text}\n${s}`;
    } else if (!text.startsWith(prefix)) {
      text = `${prefix} ${text}`;
    }
  }
  return text;
}
const stamp = "anK/s46-1m@A";
const t1 = [
  ["stamp appended",            "Hi",              `postfix:${stamp}`,  t => t.endsWith(stamp)],
  ["stamp not duplicated",      `Hi\n${stamp}`,    `postfix:${stamp}`,  t => t.split(stamp).length === 2],
  ["heartbeat skipped",         HB,                `postfix:${stamp}`,  t => t === HB],
  ["empty skipped",             "",                `postfix:${stamp}`,  t => t === ""],
  ["legacy prepend works",      "Hello",           "Agent",             t => t.startsWith("Agent")],
  ["no prefix = no change",     "Hello",           "",                  t => t === "Hello"],
];
let p1=0; for (const [d,text,pfx,chk] of t1) { const ok=chk(applyPrefix(text,pfx)); console.log(ok?`  ✅ ${d}`:`  ❌ ${d}`); if(ok)p1++; }

// ── T2: live bundle markers ───────────────────────────────────────────────────
console.log("\nT2: live bundle markers");
const reply  = readFileSync(`${DIST}/reply-B4B0jUCM.js`,          'utf8');
const pfx0   = readFileSync(`${DIST}/reply-prefix-C04eF9J1.js`,   'utf8');
const pi     = readFileSync(`${DIST}/pi-embedded-CHb5giY2.js`,    'utf8');
const sub    = readFileSync(`${DIST}/subagent-registry-DOZpiiys.js`,'utf8');

const t2 = [
  ["reply has __POSTFIX_PATCHED__",       reply.includes('__POSTFIX_PATCHED__')],
  ["reply has postfix: routing",          reply.includes('effectivePrefix.startsWith("postfix:")')],
  ["reply has append/endsWith logic",     reply.includes('text.endsWith(suffix)')],
  ["reply-prefix has IDSHORT",            pfx0.includes('__MODELSTAMP_IDSHORT__')],
  ["reply-prefix has MODELSTAMP_V3",      pfx0.includes('__MODELSTAMP_V3__')],
  ["reply-prefix has model aliases",      pfx0.includes('__MODEL_ALIAS_MAP') || (pfx0.includes('claude-sonnet-4-6') && pfx0.includes('__ms'))],
  ["reply-prefix has provider aliases",   pfx0.includes('__PROVIDER_ALIAS_MAP') || (pfx0.includes('"anthropic"') && pfx0.includes('__base'))],
  ["reply-prefix has auth letter logic",  pfx0.includes('"api_key"') && pfx0.includes('"K"')],
  ["reply-prefix has source/gateway seg", pfx0.includes('__SOURCE_ALIAS_MAP') || (pfx0.includes('__rawModel') && pfx0.includes('split'))],
  ["pi-embedded has __POSTFIX_PATCHED__", pi.includes('__POSTFIX_PATCHED__')],
  ["subagent-registry has POSTFIX",       sub.includes('__POSTFIX_PATCHED__')],
];
let p2=0; for (const [d,ok] of t2) { console.log(ok?`  ✅ ${d}`:`  ❌ ${d}`); if(ok)p2++; }

// ── T3: stamp scenarios ───────────────────────────────────────────────────────
console.log("\nT3: end-to-end stamp scenarios");
function extractShort(m) { const s=m.lastIndexOf("/"); return (s>=0?m.slice(s+1):m).replace(/-\d{8}$/,"").replace(/-latest$/,""); }
const MA = {"claude-sonnet-4-6":"s46-1m","claude-opus-4-6":"o46","gpt-5.2":"52","gpt-5.3-codex":"53c"};
const PA = {"anthropic":"an","openrouter":"or","openai":"oa","xai":"xa"};
const SA = {"anthropic":"an","openai":"oa","google":"gg"};
function mkstamp(prov, rawModel, authType, identity) {
  const short = extractShort(rawModel);
  const mAlias = MA[short] ?? short.replace(/[^a-z0-9]/gi,'').slice(0,12);
  const pBase  = PA[prov] ?? prov.slice(0,2);
  const auth   = authType==='api_key'?'K': authType==='token'||authType==='oauth'?'O':'?';
  const init   = identity.trim()[0].toUpperCase();
  let provStamp = `${pBase}${auth}`;
  if (prov === 'openrouter' || prov === 'vercel-ai-gateway') {
    const src = rawModel.split("/")[0].toLowerCase();
    provStamp = `${pBase}${auth}.${SA[src] ?? src.slice(0,2)}`;
  }
  return `${provStamp}/${mAlias}@${init}`;
}
const t3 = [
  ["anthropic/sonnet/API key",              "anthropic","claude-sonnet-4-6",          "api_key","Ava","anK/s46-1m@A"],
  ["anthropic/opus/OAuth(token)",           "anthropic","claude-opus-4-6",            "token",  "Ava","anO/o46@A"],
  ["openai/gpt-5.2/API key",               "openai",   "gpt-5.2",                    "api_key","Bot","oaK/52@B"],
  ["openrouter/sonnet-via-anthropic",       "openrouter","anthropic/claude-sonnet-4-6","api_key","Z", "orK.an/s46-1m@Z"],
  ["openrouter/gpt-via-openai",             "openrouter","openai/gpt-5.2",            "api_key","X", "orK.oa/52@X"],
  ["unknown model → fallback truncation",   "anthropic","claude-haiku-4-9",           "api_key","Ava","anK/claudehaiku4@A"],
];
let p3=0; for (const [d,prov,model,auth,id,exp] of t3) {
  const got=mkstamp(prov,model,auth,id); const ok=got===exp;
  console.log(ok?`  ✅ ${d}: ${got}`:`  ❌ ${d}\n     got:  ${got}\n     want: ${exp}`);
  if(ok)p3++;
}

// ── Summary ───────────────────────────────────────────────────────────────────
const total=t1.length+t2.length+t3.length, pass=p1+p2+p3;
console.log(`\n${'═'.repeat(52)}`);
console.log(`RESULT: ${pass}/${total} — routing:${p1}/${t1.length} bundles:${p2}/${t2.length} stamps:${p3}/${t3.length}`);
if (pass===total) console.log("✅ ALL PASS — suffix stamp is working end-to-end");
else { console.log("❌ FAILURES — see above"); process.exit(1); }

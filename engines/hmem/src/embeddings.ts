// Deterministic mock embedder: FNV-1a hash per token into a 64-dim vector,
// summed and L2-normalized. Pure function of the input text, so retrieval
// scores are reproducible across runs and machines. Swap in a real provider
// by replacing embed() in your own implementation; the contract is just
// text -> number[].

// CHANGED FROM THE UPSTREAM REFERENCE (see NOTICE): embed() is replaced by a care-domain embedder.
// The upstream hash embedder is a pure bag-of-words with collisions: it cannot tell "anxious" from "exams",
// and the spec says embedders are meant to be swapped. This one is still deterministic and offline:
//   dims 0..N_CONCEPTS-1  a concept axis each (anxiety, sleep, low mood, loneliness, ...). Any word that
//                         starts with one of a concept's stems lights that axis, so "worried", "nervous"
//                         and "stressed" land together, and "sleeping", "tired" and "night" land together
//   remaining dims        hashed stems of every other content word, so unlisted words still match literally
// tokenize() below is unchanged from upstream: the keyword/tag/entity signals of the ranking still use it.

const DIM = 64;

export function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((t) => t.length > 1);
}

const CONCEPTS: string[][] = [
  /* 0  anxiety     */ ["anxi", "worr", "nervous", "nerve", "panic", "stress", "tens", "afraid", "fear", "scare", "scari", "overwhelm", "restless", "dread"],
  /* 1  sleep       */ ["sleep", "insomn", "tired", "exhaust", "fatigue", "rest", "awake", "wake", "night", "bed", "nap", "dream", "nightmar", "drowsy", "energ"],
  /* 2  low mood    */ ["sad", "down", "depress", "hopeless", "empty", "cry", "tear", "unhappy", "miser", "low", "grie", "numb", "hurt"],
  /* 3  loneliness  */ ["lone", "alone", "isolat", "abandon", "friendless", "nobody", "withdraw", "miss"],
  /* 4  family      */ ["famil", "mother", "father", "mom", "dad", "parent", "brother", "sister", "child", "husband", "wife", "home"],
  /* 5  school/work */ ["school", "exam", "test", "study", "class", "teacher", "grade", "homework", "universit", "college", "work", "job", "boss", "career", "unemploy"],
  /* 6  money       */ ["money", "rent", "fee", "pay", "debt", "afford", "poor", "income", "financ"],
  /* 7  health      */ ["health", "sick", "ill", "pain", "ache", "doctor", "hospital", "medic", "body"],
  /* 8  anger       */ ["anger", "angry", "mad", "furious", "irritat", "rage", "frustrat", "annoy", "resent"],
  /* 9  relations   */ ["friend", "relationship", "partner", "boyfriend", "girlfriend", "breakup", "argu", "fight", "trust", "love", "marri"],
  /* 10 calming     */ ["breath", "relax", "meditat", "calm", "mindful", "pray", "yoga", "ground", "stretch"],
  /* 11 physical    */ ["walk", "exercis", "run", "jog", "swim", "garden", "sport", "football", "stretch"],
  /* 12 support     */ ["talk", "share", "listen", "support", "church", "communit", "counsel", "therap", "help", "advice"],
  /* 13 faith       */ ["god", "church", "pray", "faith", "bible", "hope", "spirit"],
  /* 14 self-worth  */ ["worthless", "useless", "failure", "fail", "ashamed", "shame", "guilt", "blame", "burden", "confiden", "proud"],
  /* 15 rumination  */ ["focus", "concentrat", "distract", "mind", "thought", "think", "ruminat", "overthink"],
  /* 16 routine     */ ["morning", "evening", "daily", "routine", "weekend", "schedule"],
  /* 17 creative    */ ["music", "sing", "song", "danc", "draw", "paint", "writ", "journal", "read", "choir"],
];
const N_CONCEPTS = CONCEPTS.length;

const STOP = new Set(("am is are was were be been the an to of and in on at my me you your it its that this with for as but if we they he she his her " +
  "their our from not no do does did have has had will would should can could cannot feel feels feeling felt very really much lot often always " +
  "lately today just so when before after about than then there here what when how who").split(/\s+/));

function stem(t: string): string {
  for (const suf of ["ing", "ed", "ly", "es", "s"]) {
    if (t.length > suf.length + 3 && t.endsWith(suf)) return t.slice(0, -suf.length);
  }
  return t;
}

function fnv1a(str: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

export function embed(text: string): number[] {
  const vec = new Array<number>(DIM).fill(0);
  const hashed = DIM - N_CONCEPTS;
  for (const raw of tokenize(text)) {
    if (STOP.has(raw)) continue;
    let matched = false;
    for (let c = 0; c < N_CONCEPTS; c++) {
      if (CONCEPTS[c].some((p) => raw.startsWith(p))) {
        vec[c] += 2;
        matched = true;
      }
    }
    if (!matched) {
      const h = fnv1a(stem(raw));
      vec[N_CONCEPTS + (h % hashed)] += 1;
    }
  }
  const norm = Math.sqrt(vec.reduce((s, v) => s + v * v, 0));
  return norm === 0 ? vec : vec.map((v) => v / norm);
}

export function cosine(a: number[], b: number[]): number {
  let dot = 0;
  for (let i = 0; i < a.length; i++) dot += a[i] * b[i];
  return dot; // both vectors are unit-length
}

export function jaccard(a: Iterable<string>, b: Iterable<string>): number {
  const sa = new Set(a);
  const sb = new Set(b);
  if (sa.size === 0 || sb.size === 0) return 0;
  let inter = 0;
  for (const x of sa) if (sb.has(x)) inter++;
  return inter / (sa.size + sb.size - inter);
}

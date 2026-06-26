"""Regenerate the common-word IPA table consumed by src/worker.py.

Offline tool (not shipped to the Worker). Builds phonetic transliterations for
the most common English words from the CMU Pronouncing Dictionary, driving the
same character tables defined in src/worker.py from real phonemes instead of
spelling. Prints a JSON dict to /tmp/common_words_ipa.json plus a sample.

Inputs (download first):
  /tmp/cmudict.dict   https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict
  /tmp/freq_full.txt  https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-usa.txt
"""

import types, sys, re

# --- load worker.py tables with JS stubbed ---
class S:
    def __getattr__(s,_): return s
    def __call__(s,*a,**k): return s
js=types.ModuleType('js'); js.Response=js.URL=js.Object=S(); sys.modules['js']=js
p=types.ModuleType('pyodide'); f=types.ModuleType('pyodide.ffi'); f.to_js=lambda o,**k:o
sys.modules['pyodide']=p; sys.modules['pyodide.ffi']=f
sys.path.insert(0, '/home/matt/receiptify/src')
import worker as W

TRANSLIT=W.TRANSLIT; FINAL_CHAR=W.FINAL_CHAR; INITIAL_CHAR=W.INITIAL_CHAR
_char_for=W._char_for; _add_nasal=W._add_nasal

VOWELS={'AA','AE','AH','AO','AW','AY','EH','ER','EY','IH','IY','OW','OY','UH','UW'}
VCORE={'AA':'a','AE':'a','AH':'a','AO':'o','AW':'ao','AY':'ai','EH':'e','ER':'e',
       'EY':'ei','IH':'i','IY':'i','OW':'ou','OY':'oi','UH':'u','UW':'u'}
ONSET={'B':'b','CH':'ch','D':'d','DH':'z','F':'f','G':'g','HH':'h','JH':'zh','K':'k',
       'L':'l','M':'m','N':'n','P':'p','R':'l','S':'s','SH':'sh','T':'t','TH':'s',
       'V':'w','W':'w','Y':'y','Z':'z','ZH':'zh'}
CODA={'B':'布','CH':'奇','D':'德','DH':'斯','F':'弗','G':'格','HH':'赫','JH':'奇',
      'K':'克','L':'尔','M':'姆','N':'恩','NG':'恩','P':'普','S':'斯','SH':'什',
      'T':'特','TH':'斯','V':'夫','Z':'兹','ZH':'日','Y':'伊','W':'沃','R':''}

ARPABET_TO_IPA = {
    'AA': 'ɑ', 'AE': 'æ', 'AH': 'ʌ', 'AO': 'ɔ', 'AW': 'aʊ', 'AY': 'aɪ',
    'EH': 'ɛ', 'ER': 'ɝ', 'EY': 'eɪ', 'IH': 'ɪ', 'IY': 'i', 'OW': 'oʊ',
    'OY': 'ɔɪ', 'UH': 'ʊ', 'UW': 'u', 'AX': 'ə', 'AXR': 'ɚ', 'AYR': 'aɪɚ',
    'AU': 'aʊ',
    'B': 'b', 'CH': 'tʃ', 'D': 'd', 'DH': 'ð', 'F': 'f', 'G': 'ɡ',
    'HH': 'h', 'JH': 'dʒ', 'K': 'k', 'L': 'l', 'M': 'm', 'N': 'n',
    'NG': 'ŋ', 'P': 'p', 'R': 'ɹ', 'S': 's', 'SH': 'ʃ', 'T': 't',
    'TH': 'θ', 'V': 'v', 'W': 'w', 'Y': 'j', 'Z': 'z', 'ZH': 'ʒ'
}

def base(ph): return re.sub(r'\d','',ph)

def phones_to_ipa(phones):
    out = []
    for ph in phones:
        stress = re.search(r'(\d)', ph)
        core = base(ph)
        ipa = ARPABET_TO_IPA.get(core)
        if not ipa:
            continue
        if stress:
            if stress.group(1) == '1':
                ipa = 'ˈ' + ipa
            elif stress.group(1) == '2':
                ipa = 'ˌ' + ipa
        out.append(ipa)
    return ''.join(out)

def phon_to_hanzi(phones):
    ph=[p for p in phones]
    n=len(ph); i=0; out=[]
    while i<n:
        p=base(ph[i])
        if p in VOWELS:
            initial=''; is_v=False; vphone=p; core=VCORE[p]; i+=1
        elif p in ONSET:
            nxt = base(ph[i+1]) if i+1<n else None
            if nxt in VOWELS:
                is_v=(p=='V'); initial=ONSET[p]
                # -tion / -sion : sibilant + schwa + final N -> 申 / 真
                if p in ('SH','ZH','CH','JH') and ph[i+1]=='AH0' and i+2<n and base(ph[i+2])=='N' and i+3==n:
                    out.append({'SH':'申','ZH':'真','JH':'真','CH':'申'}[p]); i+=3; continue
                i+=1; vphone=base(ph[i]); core=VCORE[base(ph[i])]; i+=1
            else:
                if p=='R': i+=1; continue
                out.append(CODA.get(p,'')); i+=1; continue
        else:
            i+=1; continue
        if is_v and core in ('i','e','ei'): core='ei'
        final=core
        if i<n:
            nb=base(ph[i])
            if nb=='N' and not (i+1<n and base(ph[i+1]) in VOWELS):
                final=_add_nasal(core,'n'); i+=1
            elif nb=='NG' and not (i+1<n and base(ph[i+1]) in VOWELS):
                final=_add_nasal(core,'ng'); i+=1
        if final==core:  # no nasal coda consumed
            if vphone=='EH' and (initial+'ei') in TRANSLIT:
                final='ei'
            elif vphone=='EY' and (initial+'ei') not in TRANSLIT and (initial+'ai') in TRANSLIT:
                final='ai'
        out.append(_char_for(initial,final))
    return ''.join(c for c in out if c)

# load cmudict (first pronunciation per word)
cmu={}
for line in open('/tmp/cmudict.dict'):
    line=line.split('#')[0].strip()
    if not line: continue
    parts=line.split()
    w=parts[0]
    if '(' in w: continue  # alt pronunciations word(2)
    cmu.setdefault(w.lower(), parts[1:])

# spot check
for word in ['hello','strong','nation','vision','computer','beautiful','water','people',
             'because','important','development','government','question','information',
             'language','available','community','example','business','different',
             'family','friend','money','little','great','world','music','video',
             'science','machine','data','table','apple','orange','banana','chocolate',
             'love','very','good','morning','thank','seven','red','dog','fish','king',
             'about','America','president','national','education','international']:
    pr=cmu.get(word.lower())
    print(f"{word:14} {' '.join(pr) if pr else '(no pron)':28} -> {phon_to_hanzi(pr) if pr else '—'}")

# ---- build the COMMON_WORD_PHONEMES table from the top-N frequency list ----
import worker as WW
existing = set(WW.WORD_OVERRIDES.keys())
freq = [w.strip().lower() for w in open('/tmp/freq_full.txt') if w.strip()]
table = {}
missing = 0
N = 5000
for w in freq[:N]:
    if not re.fullmatch(r"[a-z]+", w):
        continue
    if w in existing:
        continue
    pr = cmu.get(w)
    if not pr:
        missing += 1
        continue
    hz = phon_to_hanzi(pr)
    if not hz:
        continue
    ipa = phones_to_ipa(pr)
    if not ipa:
        continue
    table[w] = {
        'phones': pr,
        'ipa': ipa,
    }

print(f"# generated {len(table)} entries (skipped {missing} without pronunciations)")
import json
json.dump(table, open('/tmp/common_words_ipa.json','w'), ensure_ascii=False)

# broad sample across the frequency range
import itertools
keys = list(table.keys())
sample_idx = list(range(0, len(keys), max(1, len(keys)//45)))
for i in sample_idx:
    k = keys[i]
    print(f"{k:16} -> {table[k]['ipa']} -> {table[k]['phones']}")

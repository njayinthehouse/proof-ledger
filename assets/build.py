#!/usr/bin/env python3
"""Build a proof ledger page, and de-LaTeX a paper's proofs on the way in.

  build.py build   ledger.json [-o ledger.html]
  build.py extract paper.txt ranges.json [-o proofs.json]

`ranges.json` maps each result number to the [first, last] source lines of its
statement-and-proof, e.g. {"17": [2771, 2786]}.  Line numbers are 1-based and
the last line is exclusive, so consecutive results can share a boundary.
"""
import argparse, json, re, sys
from pathlib import Path

# ---------------------------------------------------------------- de-LaTeX
# Tuned for text pulled from an arXiv HTML rendering, where formulas survive as
# LaTeX in `alttext`.  Add rows for whatever notation the paper actually uses;
# longer patterns must come before the shorter ones they contain.
SUB = [
    (r'\\mathop\{\\stackrel\{\{\\scriptstyle\\equiv\}\}\{\{\\longrightarrow\\hskip-11\.99998pt\\rightarrow\\hskip 1\.99997pt\}\}\}', '⟶≡↠'),
    (r'\\mathop\{\\stackrel\{\{\\scriptstyle\\leq\}\}\{\{\\longrightarrow\\hskip-11\.99998pt\\rightarrow\\hskip 1\.99997pt\}\}\}', '⟶≤↠'),
    (r'\\mathop\{\\stackrel\{\{\\scriptstyle\\equiv\}\}\{\{\\longrightarrow\}\}\}', '⟶≡'),
    (r'\\mathop\{\\stackrel\{\{\\scriptstyle\\leq\}\}\{\{\\longrightarrow\}\}\}', '⟶≤'),
    (r'\\leq\^\{\*\}_\{\\mathrm\{wf\}\}', '≤*wf'), (r'\\leq_\{\\mathrm\{wf\}\}', '≤wf'),
    (r'\\equiv_\{\\mathrm\{wf\}\}', '≡wf'), (r'\\leq\^\{\*\}', '≤*'),
    (r'\\mathsf\{Top\}', '⊤'), (r'\\top', '⊤'),
    (r'\\mathrm\{([A-Za-z]+)\}', r'\1'), (r'\\mathsf\{([A-Za-z]+)\}', r'\1'),
    (r'\\mapsto', '↦'), (r'\\vdash', '⊢'), (r'\\rightarrowtail', '↣'),
    (r'\\vartriangleleft', '◁'), (r'\\backslash', lambda m: chr(92)),
    (r'\\varepsilon', 'ε'), (r'\\lambda', 'λ'),
    (r'\\alpha', 'α'), (r'\\beta', 'β'), (r'\\gamma', 'γ'), (r'\\delta', 'δ'),
    (r'\\Gamma', 'Γ'), (r'\\Delta', 'Δ'), (r'\\sigma', 'σ'), (r'\\tau', 'τ'),
    (r'\\not=', '≠'), (r'\\neq', '≠'), (r'\\not\\in', '∉'), (r'\\in', '∈'),
    (r'\\subseteq', '⊆'), (r'\\cup', '∪'), (r'\\square', '□'), (r'\\mid', '|'),
    (r'\\equiv', '≡'), (r'\\leq', '≤'), (r'\\ast', '*'), (r'\\cdot', '·'),
    (r'\\textup\{([^}]*)\}', r'\1'), (r'\\emph\{([^}]*)\}', r'\1'),
    (r'\\,', ' '), (r'\\;', ' '), (r'\\ ', ' '), (r'\\!', ''), (r'\\quad', ' '),
    (r'\\hskip[^ ]* ?', ''), (r'\\scriptstyle', ''), (r'\\lx@inpgf@ignorespaces', ''),
]
DIGITS = {c: d for c, d in zip('0123456789', '₀₁₂₃₄₅₆₇₈₉')}
OPS = ('≤*wf', '≤wf', '≡wf', '⟶≡↠', '⟶≤↠', '⟶≡', '⟶≤', '↣', '⊢', '↦')

def delatex(t: str) -> str:
    for pat, rep in SUB:
        t = re.sub(pat, rep, t)
    t = re.sub(r'\^\{\\prime\\prime\}', '″', t)
    t = re.sub(r'\^\{\\prime\}', '′', t)
    t = re.sub(r'\{\\lx@inpgf@ignorespaces ([^}]*)\}', r'\1', t)
    t = re.sub(r'_\{([^}]*)\}',
               lambda m: ''.join(DIGITS.get(c, c) for c in m.group(1))
                          if all(c in DIGITS for c in m.group(1)) else '_' + m.group(1), t)
    t = re.sub(r'_([0-9])', lambda m: DIGITS[m.group(1)], t)
    t = re.sub(r'\{([^{}]*)\}', r'\1', t)
    t = re.sub(r'\\[a-zA-Z@]+', '', t)
    t = t.replace('~', ' ')
    # macro-stripping eats the thin spaces that separate juxtaposed terms; put them back
    for op in OPS:
        t = re.sub(re.escape(op) + r'(?=[A-Za-zΓΔΛαβγδλ⊤(])', op + ' ', t)
    t = re.sub(r'≤\*(?!wf)(?=[A-Za-zΓΔαβλ⊤(])', '≤* ', t)
    t = re.sub(r'(?<=[A-Za-z0-9′″₀₁₂₃₄₅₆₇₈₉)ΓΔαβγδ⊤])(?=(⟶|↦|↣|⊢))', ' ', t)
    t = re.sub(r'(?<=[A-Za-z0-9′″₀₁₂₃₄₅₆₇₈₉)⊤])(?=[≤≡])', ' ', t)
    t = re.sub(r'(?<=[≤≡])(?=[λΓΔ(αβγδ⊤])', ' ', t)
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r' +([,.;])', r'\1', t)
    return t.strip()

def cmd_extract(a):
    lines = Path(a.paper).read_text().split('\n')
    ranges = json.loads(Path(a.ranges).read_text())
    out = {}
    for n, (lo, hi) in ranges.items():
        body = [delatex(x) for x in lines[lo - 1:hi - 1]]
        out[str(n)] = [x for x in body if x]
    Path(a.o or 'proofs.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"extracted {len(out)} proofs -> {a.o or 'proofs.json'}")

# ---------------------------------------------------------------- assemble
def overlay(led, ann):
    """Judgements written by hand, laid over facts read off the sources.

    Only fields present in the annotations are touched, so a re-derivation
    refreshes every derived fact without disturbing a single written word."""
    for k, v in ann.get('meta', {}).items():
        led.setdefault('meta', {})[k] = v
    byid = {str(n['id']): n for n in led['nodes']}
    for nid, patch in ann.get('nodes', {}).items():
        if nid in byid:
            byid[nid].update(patch)
    for nid, patch in ann.get('detail', {}).items():
        if nid in led['detail']:
            led['detail'][nid].update(patch)
    for nid, extra in ann.get('deps', {}).items():
        led.setdefault('deps', {})[nid] = sorted(set(led.get('deps', {}).get(nid, [])) | set(extra),
                                                 key=lambda s: [int(p) for p in str(s).split('.')])
    return led

def cmd_build(a):
    here = Path(__file__).parent
    tpl = (here / 'template.html').read_text()
    led = json.loads(Path(a.ledger).read_text())
    if a.annotations:
        led = overlay(led, json.loads(Path(a.annotations).read_text()))

    # ids are opaque labels — "17" and "4.3" are both fine — so compare as strings
    ids = {str(n['id']) for n in led['nodes']}
    problems = []
    for c, ps in led.get('deps', {}).items():
        if str(c) not in ids:
            problems.append(f"deps mentions unknown result {c}")
        for p in ps:
            if str(p) not in ids:
                problems.append(f"result {c} depends on unknown result {p}")
    norm = lambda s: re.sub(r'\s+', ' ', s).strip()
    for k, v in led.get('detail', {}).items():
        text = norm(' '.join(v.get('paper', [])))
        for f in v.get('faults', []):
            if norm(f['q']) not in text:
                problems.append(f"result {k}: fault quote not found in the extracted proof — {f['q'][:60]!r}")
    for n in led['nodes']:
        if n['status'] == 'refuted' and not n.get('defect'):
            problems.append(f"result {n['id']} is refuted but names no invalid step")
        if not n.get('name'):
            problems.append(f"result {n['id']} has no short name — annotate it")
    if problems:
        print("REFUSING TO BUILD:", file=sys.stderr)
        for p in problems:
            print("  ·", p, file=sys.stderr)
        sys.exit(1)

    html = (tpl.replace('{{TITLE}}', led['meta']['title'])
               .replace('{{LEDGER_JSON}}', json.dumps(led, ensure_ascii=False, separators=(',', ':'))))
    out = a.o or 'ledger.html'
    Path(out).write_text(html)
    print(f"{len(led['nodes'])} results, "
          f"{sum(len(v) for v in led.get('deps', {}).values())} edges -> {out}")

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('ledger'); b.add_argument('-o'); b.add_argument('--annotations')
    b.set_defaults(fn=cmd_build)
    e = sub.add_parser('extract')
    e.add_argument('paper'); e.add_argument('ranges'); e.add_argument('-o')
    e.set_defaults(fn=cmd_extract)
    args = ap.parse_args(); args.fn(args)

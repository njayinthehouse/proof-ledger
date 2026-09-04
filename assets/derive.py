#!/usr/bin/env python3
"""Derive a ledger skeleton from a paper and a proof development.

  derive.py --paper paper.txt --agda MPSS [--map map.json] [-o skeleton.json]

Reads the paper for its numbered results and their proofs, reads the development
for what was proved about each, and cross-references the two.  Everything it
emits is re-derivable; nothing in it is a judgement.  Judgements — the prose
account of a proof, the sentence a fault sits on, a transcribed step — belong in
a separate annotations file that `build.py` overlays on top.

The result -> definition mapping follows a naming convention (Lemma 24 -> Lem-24,
Theorem 3 -> Thm-3, Proposition 27 -> Prop-27, and `·` for a dotted number), which
`--map` overrides per result.
"""
import argparse, json, re, sys
from pathlib import Path
from build import delatex          # same directory

KIND = {'Lemma': 'Lem', 'Theorem': 'Thm', 'Proposition': 'Prop', 'Conjecture': 'Conj'}
HDR  = re.compile(r'^(Lemma|Theorem|Proposition|Conjecture)\s+(\d+(?:\.\d+)?)\s*[.(\[]')

# ---------------------------------------------------------------- the paper
def read_paper(path):
    lines = Path(path).read_text().split('\n')
    hits = [(i, m.group(1), m.group(2))
            for i, l in enumerate(lines) if (m := HDR.match(l))]
    if not hits:
        sys.exit("no numbered results found — check the paper's plain-text rendering")
    # a result may be stated in the body and proved in an appendix; keep the longest span
    spans, first_kind, renamed = {}, {}, []
    for k, (i, kind, num) in enumerate(hits):
        end = hits[k + 1][0] if k + 1 < len(hits) else len(lines)
        if num not in first_kind:
            first_kind[num] = kind
        elif first_kind[num] != kind:
            renamed.append(f'{num}: stated as {first_kind[num]} {num}, restated as {kind} {num}')
        # a result may be stated in the body and proved in an appendix, and the body
        # statement may be followed by pages of discussion. Prefer the span that
        # actually contains a proof; fall back to the longest.
        has_proof = any(re.match(r'^Proof', lines[k]) for k in range(i, end))
        if num not in spans:
            spans[num] = (i, end, has_proof)
        else:
            old_i, old_end, old_proof = spans[num]
            better = (has_proof and not old_proof) or \
                     (has_proof == old_proof and end - i > old_end - old_i)
            if better:
                spans[num] = (i, end, has_proof)
    out = {}
    for num, (i, end, _) in spans.items():
        body = [delatex(x) for x in lines[i:end]]
        out[num] = {'kind': first_kind[num], 'paper': [x for x in body if x]}
    return out, renamed

def cites(proof_lines, num):
    text = ' '.join(proof_lines)
    found = set(re.findall(r'(?:Lemma|Theorem|Proposition|Conjecture)\s+(\d+(?:\.\d+)?)', text))
    return sorted(found - {num}, key=sortkey)

sortkey = lambda s: [int(p) for p in s.split('.')]

# ---------------------------------------------------------------- the proofs
DEFN = re.compile(r'^([^\s:()\[\]{}]+)\s*:(?!=)(.*)$')

MODSTART = re.compile(r'^(\s*)module\s+_\s')

def module_graph(root):
    """Module -> modules it can see, from `open import` lines.

    Definition-level edges are found by scanning bodies for names, which cannot
    distinguish a reference from a coincidence of spelling. A reference is only
    possible if the referring module can actually see the referenced one, so the
    import graph is a sound filter on the lexical scan."""
    imports, reach = {}, {}
    for f in sorted(Path(root).rglob('*.lagda.md')):
        mod = str(f.with_suffix('').with_suffix('')).replace('/', '.')
        imports[mod] = set(re.findall(r'^\s*(?:open\s+)?import\s+([\w.]+)', f.read_text(), re.M))
    def visit(m, acc):
        for d in imports.get(m, ()):
            if d not in acc:
                acc.add(d); visit(d, acc)
        return acc
    for m in imports:
        reach[m] = visit(m, {m})
    return reach


def read_agda(root):
    """name -> {module, sig, body, hyps}.

    `hyps` are the parameters of the enclosing anonymous module, if any: a proof
    written inside `module _ (h : H) where` is a proof *conditional on* H, and the
    ledger should say so rather than call it unconditional."""
    index, statements = {}, set()
    for f in sorted(Path(root).rglob('*.lagda.md')):
        mod = str(f.with_suffix('').with_suffix('')).replace('/', '.')
        lines = f.read_text().split('\n')
        i, inside, mod_params, mod_indent = 0, False, [], -1
        while i < len(lines):
            l = lines[i]
            if l.startswith('```'):
                inside = l.startswith('```agda'); i += 1; continue
            if inside and (mh := MODSTART.match(l)):
                # a module header may run over several lines; read to `where`
                head, j = [l], i
                while 'where' not in head[-1] and j + 1 < len(lines):
                    j += 1; head.append(lines[j])
                mod_indent = len(mh.group(1))
                # keep the parameter's type: only those whose type is a declared
                # statement are real hypotheses, the rest are scoping side conditions
                mod_params = [(n.strip(), ty.strip())
                              for grp, ty in re.findall(r'\(([^:()]+):([^()]*)\)', ' '.join(head))
                              for n in grp.split()]
                i = j + 1; continue
            if inside and l.strip() and mod_indent >= 0 \
               and (len(l) - len(l.lstrip())) <= mod_indent:
                mod_params, mod_indent = [], -1
            m = DEFN.match(l.lstrip()) if inside and l.strip() else None
            if m:
                indent = len(l) - len(l.lstrip())
                name = m.group(1)
                sig = [l.rstrip()]
                j = i + 1
                while j < len(lines) and lines[j].strip() and not lines[j].startswith('```') \
                        and len(lines[j]) - len(lines[j].lstrip()) > indent:
                    sig.append(lines[j].rstrip()); j += 1
                body = []
                while j < len(lines) and not lines[j].startswith('```'):
                    nxt = lines[j]
                    if nxt.strip() and (len(nxt) - len(nxt.lstrip())) <= indent \
                       and DEFN.match(nxt.lstrip()) and not nxt.lstrip().startswith(name + ' '):
                        break
                    body.append(nxt); j += 1
                entry = {'module': mod, 'sig': '\n'.join(sig), 'body': '\n'.join(body),
                         'hyps': list(mod_params)}
                if is_statement(entry):
                    statements.add(name)     # every declared statement, even where a proof shares its name
                # a proof beats a bare statement of the same name
                if name not in index or is_statement(index[name]):
                    index[name] = entry
                i = j; continue
            i += 1
    return index, statements

def candidates(kind, num):
    stem = KIND[kind]
    dotted = num.replace('.', '·')
    return [f'{stem}-{dotted}', f'{stem}-{num}',
            f'{stem.lower()}-{dotted}-false', f'{stem.lower()}-{num}-false',
            f'{stem}-{dotted}ʳ']

def is_statement(entry):
    """`X : Set` declares a statement; it is not a proof of it."""
    head = entry['sig'].split(':', 1)[1] if ':' in entry['sig'] else ''
    return re.fullmatch(r'\s*Set[₀-₉0-9]*\s*', head.split('\n')[0]) is not None

REFUTES = re.compile(r'-(false|fails)$')

def classify(name, entry):
    """A `¬` in the type proves nothing about the paper.

    Plenty of true theorems are negative — "no supertype of ⊤" is one — and plenty
    of proofs take a negation as a *hypothesis*. Whether our statement contradicts
    the paper's is not visible in the type, so a refutation is pinned by naming
    convention (`…-false`, `…-fails`) or by `--map`, never inferred from `¬`."""
    if is_statement(entry):
        return 'open'
    return 'refuted' if REFUTES.search(name) else 'proved'

# ---------------------------------------------------------------- assemble
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--paper', required=True)
    ap.add_argument('--agda', help='a development to cross-reference; omit to derive from the paper alone')
    ap.add_argument('--map')
    ap.add_argument('--title', default='Proof Ledger')
    ap.add_argument('-o', default='skeleton.json')
    a = ap.parse_args()

    paper, renamed = read_paper(a.paper)
    if a.agda:
        index, statements = read_agda(a.agda)
        reach = module_graph(a.agda)
    else:
        index, statements, reach = {}, set(), {}
    override = json.loads(Path(a.map).read_text()) if a.map else {}

    nodes, detail, deps = [], {}, {}
    unresolved, spurious = [], []
    for num in sorted(paper, key=sortkey):
        kind = paper[num]['kind']
        names = override.get(num) or [n for n in candidates(kind, num) if n in index]
        names = [n for n in names if n in index]
        names.sort(key=lambda n: is_statement(index[n]))
        status = 'open'
        mod, sig = '—', ''
        if names:
            status = classify(names[0], index[names[0]])
            mod = index[names[0]]['module']
            sig = '\n\n'.join(index[n]['sig'] for n in names)
            hyps = sorted({ty for n in names for _, ty in index[n]['hyps']
                           if ty in statements})
        else:
            hyps = []
            unresolved.append(f'{kind} {num}')
        nodes.append({'id': num, 'ref': f'{kind} {num}', 'name': '',
                      'status': status, 'module': mod, 'defect': ''})
        detail[num] = {'module': mod, 'account': '', 'sig': sig,
                       'paper': paper[num]['paper'], 'faults': [], 'hyps': hyps}
        # dataflow: what the paper's proof cites, and what our definitions reach
        edges = set(cites(paper[num]['paper'], num))
        for n in names:
            for other in sorted(paper, key=sortkey):
                if other == num:
                    continue
                for cand in (override.get(other) or candidates(paper[other]['kind'], other)):
                    if cand in index and re.search(r'(?<![\w·-])' + re.escape(cand) + r'(?![\w·-])',
                                                   index[n]['body']):
                        here, there_ = index[n]['module'], index[cand]['module']
                        if there_ in reach.get(here, {here}):
                            edges.add(other)
                        else:
                            spurious.append(f'{num} -> {other} '
                                            f'({n} mentions {cand}, but {here} does not import {there_})')
        if edges:
            deps[num] = sorted(edges, key=sortkey)

    # Status answers "is there a proof of this in the development"; `hyps` answers
    # "what does it rest on". They are orthogonal, and openness is deliberately not
    # propagated along hypotheses — doing so whitens most of a conditional development
    # and loses the distinction between having no proof and having a conditional one.
    # A verdict that should read differently is pinned in the annotations.
    # the body scan sees mutual recursion as a cycle; the layout needs a DAG
    order, seen, stack, dropped = [], set(), set(), []
    def visit(v):
        seen.add(v); stack.add(v)
        for w in list(deps.get(v, [])):
            if w in stack:
                deps[v] = [x for x in deps[v] if x != w]; dropped.append((v, w))
            elif w not in seen:
                visit(w)
        stack.discard(v)
    for n in nodes:
        if n['id'] not in seen:
            visit(n['id'])

    led = {'meta': {'title': a.title, 'eyebrow': '', 'headline': a.title,
                    'standfirst': '',
                    'footer': ([f'{len(list(Path(a.agda).rglob("*.lagda.md")))} modules']
                               if a.agda else
                               ['derived from the paper alone — nothing mechanized yet'])},
           'nodes': nodes, 'deps': deps, 'detail': detail}
    Path(a.o).write_text(json.dumps(led, ensure_ascii=False, indent=1))
    print(f'{len(nodes)} results, {sum(len(v) for v in deps.values())} edges -> {a.o}')
    cond = [n['id'] for n in nodes if detail[n['id']]['hyps']]
    if cond:
        print('  conditional on declared statements:')
        for c in cond:
            print(f'    · {c} on ' + ', '.join(detail[c]['hyps']))
    print(f'  proved {sum(1 for n in nodes if n["status"]=="proved")}'
          f' · refuted {sum(1 for n in nodes if n["status"]=="refuted")}'
          f' · open {sum(1 for n in nodes if n["status"]=="open")}')
    if spurious:
        print('  lexical matches with no import to back them, dropped:')
        for x in spurious:
            print('    ·', x)
    if dropped:
        print('  mutual recursion in the development, one edge of each cycle dropped:')
        for v, w in dropped:
            print(f'    · {v} ↔ {w}')
    if renamed:
        print('  the paper renames a result between statements:')
        for r in renamed:
            print('    ·', r)
    if unresolved and a.agda:
        print('  no definition found for: ' + ', '.join(unresolved))
        print('  (name them in --map, or leave them open if they are genuinely unmechanized)')
    elif not a.agda:
        print('  every result is open: no development was given, so the graph is the paper\'s own')

if __name__ == '__main__':
    main()

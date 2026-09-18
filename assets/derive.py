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

# ids are labels: the paper's numbers sort numerically, a development lemma's id
# (`8a`) after them, by its leading number and then as text
def sortkey(s):
    parts = str(s).split('.')
    if all(p.isdigit() for p in parts):
        return (0, [int(p) for p in parts], '')
    m = re.match(r'\d+', str(s))
    return (1, [int(m.group())] if m else [], str(s))

# ---------------------------------------------------------------- the proofs
DEFN = re.compile(r'^([^\s:()\[\]{}]+)\s*:(?!=)(.*)$')

MODSTART = re.compile(r'^(\s*)module\s+_\s')

def agda_files(root):
    """The development's modules, plus any module they import that lives beside the
    root (a shared syntax module one directory up), so a datatype defined there is
    still found. Returns [(module name, path)]."""
    root = Path(root)
    files = {str(f.with_suffix('').with_suffix('')).replace('/', '.'): f
             for f in sorted(root.rglob('*.lagda.md'))}
    base = root.parent
    queue = list(files.values())
    while queue:
        f = queue.pop()
        for m in re.findall(r'^\s*(?:open\s+)?import\s+([\w.]+)', f.read_text(), re.M):
            if m in files:
                continue
            cand = base / (m.replace('.', '/') + '.lagda.md')
            if cand.exists():
                files[m] = cand; queue.append(cand)
    return sorted(files.items())

TYPEDECL = re.compile(r'^(data|record)\s+([^\s:]+)')

# a readable form of a mixfix name: each `_` filled by a variable chosen from the
# corresponding index type in the declaration's header, primed on repetition
TYPEVARS = {'Ctx': 'Γ', 'Stack': 's', 'Tm': 't', 'Mode': 'm', 'Name': 'x', 'List Name': 'L',
            'ℕ': 'n', 'Nat': 'n', 'Kind': 'a', 'Ty': 'A', 'Type': 'A'}
PRIMES = ['', '′', '″', '‴']

def display_name(name, header):
    if '_' not in name:
        return name
    m = re.search(r':\s*(.*?)\s*(?:\bwhere\b.*)?$', header)
    segs = [a.strip() for a in m.group(1).split('→')] if m else []
    args = segs[:-1]          # the last segment is the result: `Set` for a datatype, a type for a function
    pieces = name.split('_')
    holes = len(pieces) - 1
    used, vars_ = {}, []
    for i in range(holes):
        ty = args[i] if i < len(args) else ''
        base = TYPEVARS.get(ty) or (ty[0].lower() if ty else 'x')
        k = used.get(base, 0); used[base] = k + 1
        vars_.append(base + (PRIMES[k] if k < len(PRIMES) else str(k)))
    out = ''
    for i, piece in enumerate(pieces):
        out += piece
        if i < holes:
            out += (' ' if piece else '') + vars_[i] + (' ' if pieces[i + 1] else '')
    return out.strip()

def read_types(root):
    """name -> {module, decl}: every `data` and `record` declaration, with its
    constructors or fields, so a card can show what a statement is built from."""
    types = {}
    for mod, f in agda_files(root):
        lines = f.read_text().split('\n')
        inside = False
        i = 0
        while i < len(lines):
            l = lines[i]
            if l.startswith('```'):
                inside = l.startswith('```agda'); i += 1; continue
            m = TYPEDECL.match(l) if inside else None
            if m:
                block = [l.rstrip()]; j = i + 1
                while j < len(lines) and not lines[j].startswith('```') \
                        and (not lines[j].strip() or lines[j][0] in ' \t'):
                    block.append(lines[j].rstrip()); j += 1
                while block and not block[-1].strip():
                    block.pop()
                entry = {'module': mod, 'decl': '\n'.join(block)}
                same = [e for e in types.get(m.group(2), []) if e['module'] == mod]
                if same:
                    # a mutual block declares the type first (with its index types) and
                    # gives the constructors later: keep the typed header, add the body
                    prev = same[0]
                    header = prev['decl'].split('\n')[0] if ' : ' in prev['decl'].split('\n')[0] else block[0]
                    body = block[1:] if len(block) > 1 else prev['decl'].split('\n')[1:]
                    prev['decl'] = '\n'.join([header.replace(' where', '') + ' where'] + body) if body else header
                else:
                    types[m.group(2)] = types.get(m.group(2), []) + [entry]
                i = j; continue
            i += 1
    return types

BRACKETS = str.maketrans('', '', '()[]{}')

def mentions(text, name):
    """Whether a mixfix name occurs in a piece of Agda: its pieces, in order, as
    tokens of one arrow-segment."""
    segments = [[w.translate(BRACKETS) for w in seg.split()] for seg in re.split(r'→|=', text)]
    segments = [[w for w in seg if w] for seg in segments]
    pieces = [q.translate(BRACKETS) for q in name.split('_')]
    pieces = [q for q in pieces if q]
    if not pieces:
        return False
    for seg in segments:
        k = 0
        for w in seg:
            if k < len(pieces) and w == pieces[k]:
                k += 1
        if k == len(pieces):
            return True
    return False

ALIASES = {}   # name -> {module, body}: definitions of type `… → Set` that abbreviate a judgement
FUNCS = {}     # name -> {module, sig, body}: the functions a statement or datatype is built from

PLAIN_TARGET = re.compile(r'^(Set[₀-₉0-9]*|Tm|Ctx|Stack|Name|ℕ|Nat|Bool|Kind|Mode|CoCtx|Ann|List\b.*|Maybe\b.*)$')

def is_function(entry, types, resultnames):
    """A definition is a function, not a lemma, when its type's target is a plain type
    — a term, a context, a list, a Set — rather than a proposition."""
    if is_statement(entry) or not entry['body'].strip() or entry.get('indent', 0) > 0:
        return False
    head = entry['sig'].split(':', 1)[1] if ':' in entry['sig'] else ''
    head = ' '.join(l.strip() for l in head.split('\n')).strip()
    target = re.split(r'→', head)[-1].strip().strip('()')
    return bool(PLAIN_TARGET.match(target))

def fns_in(text, here, reach):
    return [n for n, info in FUNCS.items()
            if info['module'] in reach.get(here, {here}) and mentions(text, n)]

def types_in(sig, types, here, reach, _seen=None):
    """The declared types a signature mentions: a mixfix name `_∣_⊢_⟶ᵉ_` is
    present when its pieces occur, in order, as tokens of one arrow-segment of the
    signature, and the mentioning module can see the type's module. An abbreviation
    (`Γ ⊢ u ≋wf t = Γ ⊢ u ⊑wf[ eqv-m ] t`) is looked through to what it unfolds to."""
    seen = _seen if _seen is not None else set()
    found = []
    for alias, info in ALIASES.items():
        if alias in seen or info['module'] not in reach.get(here, {here}):
            continue
        if mentions(sig, alias):
            seen.add(alias)
            for ty in types_in(info['body'], types, info['module'], reach, seen):
                if ty['name'] not in {f['name'] for f in found}:
                    found.append(ty)
    for name, cands in types.items():
        # the same name may be declared in several modules (a calculus and its
        # ancestor); keep the ones the mentioning module can see, and of those prefer
        # the nearest — fewest imports away — which is the one Agda would resolve
        seen = reach.get(here, {here})
        vis = [c for c in cands if c['module'] in seen]
        if not vis:
            continue
        # the development's own declaration beats an ancestor's of the same name,
        # since the ancestor is normally imported with a `using` list for other things
        info = min(vis, key=lambda c: (not c['module'].startswith(ROOT_PREFIX), distance(here, c['module'])))
        if mentions(sig, name) and name not in {f['name'] for f in found}:
            found.append({'name': name, 'display': display_name(name, info['decl'].split('\n')[0]),
                          'module': info['module'], 'decl': info['decl']})
    return found

IMPORTS = {}
ROOT_PREFIX = ''


def distance(here, there):
    """Import steps from `here` to `there`, by breadth-first search over the module graph."""
    if here == there:
        return 0
    frontier, seen, d = [here], {here}, 0
    while frontier:
        d += 1; nxt = []
        for m in frontier:
            for k in IMPORTS.get(m, ()):
                if k == there:
                    return d
                if k not in seen:
                    seen.add(k); nxt.append(k)
        frontier = nxt
    return 10 ** 6

def module_graph(root):
    """Module -> modules it can see, from `open import` lines.

    Definition-level edges are found by scanning bodies for names, which cannot
    distinguish a reference from a coincidence of spelling. A reference is only
    possible if the referring module can actually see the referenced one, so the
    import graph is a sound filter on the lexical scan."""
    imports, reach = IMPORTS, {}
    for mod, f in agda_files(root):
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
    prefix = Path(root).name + '.'
    for mod, f in agda_files(root):
        external = not mod.startswith(prefix)
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
                         'hyps': list(mod_params), 'external': external,
                         'indent': indent}
                if is_statement(entry):
                    statements.add(name)     # every declared statement, even where a proof shares its name
                # a proof beats a bare statement of the same name
                # a development's own definition beats a neighbour's of the same name
                if name not in index or (is_statement(index[name]) and not external) \
                   or (index[name]['external'] and not external):
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
        types = read_types(a.agda)
        for nm, e in index.items():
            head = e['sig'].split(':', 1)[1] if ':' in e['sig'] else ''
            if re.search(r'\bSet[₀-₉0-9]*\s*$', head.strip()) and not is_statement(e) \
               and nm not in types and e['body'].strip():
                ALIASES[nm] = {'module': e['module'], 'body': e['body']}
            if nm not in types and is_function(e, types, None):
                FUNCS[nm] = {'module': e['module'], 'sig': e['sig'], 'body': e['body']}
        ctors = {m.group(1) for cs in types.values() for c in cs
                 for l in c['decl'].split('\n') for m in [re.match(r'^\s+([^\s:()]+)\s*:', l)] if m}
        for c in ctors:
            FUNCS.pop(c, None)
        # a type synonym `Ctx : Set` with a non-quantified body is a type, not a statement
        for nm, e in index.items():
            if is_statement(e) and e['body'].strip() and not re.search(r'∀|→', e['body']) \
               and not e['external'] or (nm not in types and is_statement(e) and e['body'].strip()
                                          and not re.search(r'∀|→', e['body'])):
                types.setdefault(nm, []).append({'module': e['module'], 'decl': e['sig'] + '\n' + e['body'].strip('\n')})
        global ROOT_PREFIX
        ROOT_PREFIX = Path(a.agda).name + '.'
    else:
        index, statements, reach, types = {}, set(), {}, {}
    override = json.loads(Path(a.map).read_text()) if a.map else {}
    # results the paper does not have: a supporting lemma the development proves on the
    # way to a numbered result is a node of its own, not a step in that result's log
    development = override.pop('development', [])
    for d in development:
        paper[d['id']] = {'kind': None, 'ref': d['ref'], 'paper': [], 'development': True}
        override[d['id']] = d['names']
    variants = {k.rstrip('′'): v for k, v in override.items() if k.endswith('′')}
    override = {k: v for k, v in override.items() if not k.endswith('′')}

    nodes, detail, deps, devedges = [], {}, {}, {}
    unresolved, spurious, used_names = [], [], set()
    for num in sorted(paper, key=sortkey):
        kind = paper[num]['kind']
        names = override.get(num) or [n for n in (candidates(kind, num) if kind else []) if n in index]
        names = list(dict.fromkeys(n for n in names if n in index and not index[n]['external']))
        names.sort(key=lambda n: is_statement(index[n]))
        lead = names[0] if names else None        # the verdict comes from the proof, decided here
        used_names.update(names)
        # a refutation `x-false : ¬ X` is read with the statement X it refutes, and a
        # statement `X : Set` is shown with its definition — the type alone says nothing
        for n in list(names):
            m = re.search(r'¬\s*\(?\s*([^\s()]+)', index[n]['sig'])
            if m and m.group(1) in index and is_statement(index[m.group(1)]) and m.group(1) not in names:
                names.insert(0, m.group(1))
        status = 'open'
        mod, sig = '—', ''
        def shown(n):
            e = index[n]
            if is_statement(e):
                body = '\n'.join(l.rstrip() for l in e['body'].split('\n')).strip('\n')
                return e['sig'] + ('\n' + body if body else '')
            return e['sig']
        if names:
            status = classify(lead, index[lead])
            mod = index[lead]['module']
            sig = '\n\n'.join(shown(n) for n in sorted(names, key=lambda n: not is_statement(index[n])))
            hyps = sorted({ty for n in names for _, ty in index[n]['hyps']
                           if ty in statements})
            seen_t, used = set(), []
            for n in names:
                for ty in types_in(shown(n), types, index[n]['module'], reach):
                    if ty['name'] not in seen_t:
                        seen_t.add(ty['name']); used.append(ty)
            # the variant's statement is built from its own datatypes — the edited relation
            for n in variants.get(num, []):
                if n in index:
                    for ty in types_in(shown(n), types, index[n]['module'], reach):
                        if ty['name'] not in seen_t:
                            seen_t.add(ty['name']); used.append({**ty, 'via': 'variant'})
        else:
            hyps, used = [], []
            unresolved.append(paper[num].get('ref') or f'{kind} {num}')
        nodes.append({'id': num, 'ref': paper[num].get('ref') or f'{kind} {num}', 'name': '',
                      'status': status, 'module': mod, 'defect': '',
                      **({'origin': 'development'} if paper[num].get('development') else {})})
        detail[num] = {'module': mod, 'account': '', 'sig': sig,
                       'paper': paper[num]['paper'], 'faults': [], 'hyps': hyps,
                       'types': used}
        vnames = [n for n in variants.get(num, []) if n in index]
        if vnames:
            detail[num]['variant'] = {'names': vnames,
                                      'sig': '\n\n'.join(shown(n) for n in vnames),
                                      'module': index[vnames[0]]['module']}
        # dataflow: what the paper's proof cites, and what our definitions reach
        edges = set(cites(paper[num]['paper'], num))
        for n in names:
            for other in sorted(paper, key=sortkey):
                if other == num:
                    continue
                for cand in (override.get(other) or (candidates(paper[other]['kind'], other)
                                                     if paper[other]['kind'] else [])):
                    if cand in index and re.search(r'(?<![\w·-])' + re.escape(cand) + r'(?![\w·-])',
                                                   index[n]['body']):
                        here, there_ = index[n]['module'], index[cand]['module']
                        if there_ in reach.get(here, {here}):
                            edges.add(other)
                            devedges.setdefault(num, set()).add(other)
                        else:
                            spurious.append(f'{num} -> {other} '
                                            f'({n} mentions {cand}, but {here} does not import {there_})')
        if edges:
            deps[num] = sorted(edges, key=sortkey)
    for d in development:
        for sup in d.get('supports', []):
            if sup in paper:
                deps[sup] = sorted(set(deps.get(sup, [])) | {d['id']}, key=sortkey)

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

    # the datatypes as nodes of the graph: every type some statement mentions, plus
    # the types those declarations mention in turn, with edges between them
    tnodes, tdeps = {}, {}
    def add_type(ty):
        if ty['name'] in tnodes:
            return
        base = ty['name'].replace('′', '')
        tnodes[ty['name']] = {'id': 'T:' + ty['name'], 'name': ty['name'],
                              'display': display_name(ty['name'], ty['decl'].split('\n')[0]),
                              'module': ty['module'], 'decl': ty['decl'],
                              **({'edited_from': base} if base != ty['name'] and base in types else {})}
        inner = [u for u in types_in(ty['decl'], types, ty['module'], reach) if u['name'] != ty['name']]
        tdeps['T:' + ty['name']] = sorted('T:' + u['name'] for u in inner)
        for u in inner:
            add_type(u)
    fnodes = {}
    def add_fn(name):
        if name in fnodes:
            return
        info = FUNCS[name]
        fnodes[name] = {'id': 'F:' + name, 'name': name,
                        'display': display_name(name, info['sig'].split('\n')[0]),
                        'module': info['module'], 'sig': info['sig'], 'body': info['body']}
        text = info['sig'] + '\n' + info['body']
        inner_f = [n for n in fns_in(text, info['module'], reach) if n != name]
        inner_t = types_in(text, types, info['module'], reach)
        tdeps['F:' + name] = sorted(['F:' + n for n in inner_f] + ['T:' + u['name'] for u in inner_t])
        for n in inner_f:
            add_fn(n)
        for u in inner_t:
            add_type(u)
    for num in detail:
        for ty in detail[num].get('types', []):
            add_type(ty)
    typedeps = {num: sorted('T:' + ty['name'] for ty in detail[num].get('types', []))
                for num in detail if detail[num].get('types')}
    # functions: from each result's signature, from each datatype's declaration, and onward;
    # a name that stands for a numbered result is a result, not a function
    for n in used_names:
        FUNCS.pop(n, None)
    for num in detail:
        here = detail[num]['module']
        fs = fns_in(detail[num]['sig'], here, reach) if here != '—' else []
        for n in variants.get(num, []):
            if n in index:
                fs = fs + [f for f in fns_in(index[n]['sig'], index[n]['module'], reach) if f not in fs]
        for n in fs:
            add_fn(n)
        if fs:
            typedeps[num] = sorted(set(typedeps.get(num, [])) | {'F:' + n for n in fs})
    for tn in list(tnodes.values()):
        fs = fns_in(tn['decl'], tn['module'], reach)
        for n in fs:
            add_fn(n)
        if fs:
            tdeps[tn['id']] = sorted(set(tdeps.get(tn['id'], [])) | {'F:' + n for n in fs})

    # mutual definitions: strongly connected components of the development's own
    # edges — results whose definitions call each other, datatypes declared together,
    # functions defined together. Each becomes one supercard in the graph.
    graph = {str(k): set(str(x) for x in v) for k, v in devedges.items()}
    for k, v in tdeps.items():
        graph[k] = set(v)
    def scc(graph):
        index_, low, onstack, stack, out = {}, {}, set(), [], []
        counter = [0]
        def strong(v):
            index_[v] = low[v] = counter[0]; counter[0] += 1
            stack.append(v); onstack.add(v)
            for w in graph.get(v, ()):
                if w not in index_:
                    strong(w); low[v] = min(low[v], low[w])
                elif w in onstack:
                    low[v] = min(low[v], index_[w])
            if low[v] == index_[v]:
                comp = []
                while True:
                    w = stack.pop(); onstack.discard(w); comp.append(w)
                    if w == v:
                        break
                out.append(comp)
        for v in list(graph):
            if v not in index_:
                strong(v)
        return out
    groups = [{'id': 'G:' + '+'.join(sorted(c)), 'members': sorted(c, key=lambda s: (not s[:1].isdigit(), s))}
              for c in scc(graph) if len(c) > 1]
    if groups:
        print('  mutually defined, grouped:')
        for g in groups:
            print('    · ' + ', '.join(g['members']))

    led = {'meta': {'title': a.title, 'eyebrow': '', 'headline': a.title,
                    'standfirst': '',
                    'footer': ([f'{len(list(Path(a.agda).rglob("*.lagda.md")))} modules']
                               if a.agda else
                               ['derived from the paper alone — nothing mechanized yet'])},
           'nodes': nodes, 'deps': deps, 'detail': detail,
           'types': sorted(tnodes.values(), key=lambda x: (x['module'], x['name'])),
           'functions': sorted(fnodes.values(), key=lambda x: (x['module'], x['name'])),
           'typedeps': {**typedeps, **tdeps},
           'groups': groups}
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

#!/usr/bin/env python3
"""Turn a ledger into a literate Agda skeleton, one module per result.

  scaffold.py --ledger ledger.json --out src/Paper --prefix Paper [--force]

Each result becomes a module carrying the paper's own statement, importing the
modules for the results its proof cites.  The paper's citation graph therefore
becomes the import graph, and Agda enforces from the first day that the
formalization respects it.

The skeleton typechecks as emitted: every module is empty but for its imports, so
results can be filled in one at a time and in any order.

**Types are not generated.** Turning an informal statement into a type is the
work; a plausible-looking guess would be worse than none, because it invites you
to accept it. What is emitted is the statement, verbatim, as the specification to
translate — and a commented stub to fill.
"""
import argparse, json, re, sys
from pathlib import Path

KIND = {'Lemma': 'Lem', 'Theorem': 'Thm', 'Proposition': 'Prop', 'Conjecture': 'Conj'}

def modname(ref):
    kind, num = ref.split()
    return f"{KIND.get(kind, kind[:3])}-{num.replace('.', '·')}"

def statement(lines):
    """The paper's statement: everything from the header to the proof."""
    out = []
    for l in lines[1:]:
        if re.match(r'^(Proof|∎)', l):
            break
        out.append(l)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ledger', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--prefix', required=True, help='Agda module prefix, e.g. MPSS')
    ap.add_argument('--force', action='store_true', help='overwrite modules that already exist')
    a = ap.parse_args()

    led = json.loads(Path(a.ledger).read_text())
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    byid = {str(n['id']): n for n in led['nodes']}
    deps = {str(k): [str(x) for x in v] for k, v in led.get('deps', {}).items()}

    written, kept = [], []
    for nid, n in byid.items():
        name = modname(n['ref'])
        f = out / f'{name}.lagda.md'
        if f.exists() and not a.force:
            kept.append(name); continue

        cites = deps.get(nid, [])
        imports = [f'open import {a.prefix}.{modname(byid[c]["ref"])}'
                   for c in cites if c in byid]
        body = statement(led['detail'].get(nid, {}).get('paper', []))

        doc = [f'# {n["ref"]}' + (f' — {n["name"]}' if n.get('name') else ''), '']
        if body:
            doc += ['> ' + l for l in body] + ['']
        if cites:
            doc += ['Its proof in the paper cites '
                    + ', '.join(byid[c]['ref'] for c in cites if c in byid) + '.', '']
        doc += ['Write the type below, then the proof. The statement above is the specification;',
                'nothing here was generated from it.', '',
                '```agda', '{-# OPTIONS --safe #-}', '',
                f'module {a.prefix}.{name} where', '']
        doc += imports + ([''] if imports else [])
        doc += ['```', '',
                '## The statement', '',
                '```agda',
                f'-- {name} : ?',
                f'-- {name} = ?',
                '```', '']
        f.write_text('\n'.join(doc))
        written.append(name)

    # an index so the whole skeleton can be checked with one command
    idx = out / 'All.lagda.md'
    if not idx.exists() or a.force:
        order = sorted(byid, key=lambda s: [int(p) for p in s.split('.')])
        idx.write_text('\n'.join(
            [f'# {a.prefix} — every result', '',
             'Importing this checks the whole skeleton.', '',
             '```agda', '{-# OPTIONS --safe #-}', '',
             f'module {a.prefix}.All where', ''] +
            [f'open import {a.prefix}.{modname(byid[i]["ref"])}' for i in order] +
            ['```', '']))

    print(f'{len(written)} modules written to {out}')
    if kept:
        print(f'  {len(kept)} left alone (already present): ' + ', '.join(kept[:8])
              + (' …' if len(kept) > 8 else ''))
    print(f'  check with: agda {out}/All.lagda.md')

if __name__ == '__main__':
    main()

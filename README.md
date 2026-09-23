# proof-ledger

An interactive ledger for a paper whose proofs are being machine-checked. It shows every
numbered result of the paper as a dependency graph, coloured by verdict: proved, refuted,
repaired, or still open. Click a result to see how its verdict was reached, compare any two
versions of its statement side by side, and read the paper's own proof next to the step that
fails.

A paper numbers its results for reading, not by dependency. In the paper this was built for,
73% of dependency edges cite a *higher*-numbered result, and the two propositions that turned
out false sat in the foundations with nothing in the numbering to show it. The ledger recovers
the structure the numbering hides.

**Live example:** [the MPSS ledger](https://njayinthehouse.github.io/subtype-agda/), built by CI
from [subtype-agda](https://github.com/njayinthehouse/subtype-agda) on every push, after the
whole Agda development typechecks.

## Pipeline

```
paper.txt ─┐
           ├─ derive.py ─→ ledger.json ─┐
Agda src ──┘   (facts)                  ├─ build.py ─→ ledger.html (one self-contained page)
               annotations.json ────────┘
               (judgements)
```

- **`assets/derive.py`** reads the paper's numbered results and their proofs, reads the Agda
  development for what was proved about each, and cross-references the two into `ledger.json`.
  Everything it emits is re-derivable, so `ledger.json` is disposable. Rerun it after any
  change to the proofs.
- **An annotations file** holds everything that is a judgement rather than a fact: the prose
  account of a proof, the sentence a fault sits on, a transcribed step. `build.py` overlays it
  on the derived data.
- **`assets/build.py`** validates the data and fills `assets/template.html` with it. The result is
  a single static HTML file with no server and no build step for the reader.
- **`assets/scaffold.py`** goes the other way, for a paper with nothing mechanized yet: it
  emits one literate Agda module per result, importing the modules its proof cites, so the
  paper's citation graph becomes the import graph from day one.

```
python3 assets/derive.py --paper paper.txt --agda src --map ledger-map.json -o ledger.json
python3 assets/build.py build ledger.json --annotations ledger-annotations.json -o ledger.html
```

Python 3 standard library only.

## What the build refuses

The build is also a checker. It fails on:

- a dependency on an unknown result;
- a result marked refuted with no invalid step of the paper's proof named. "The theorem is
  false" and "here is the line that does not follow" are different claims, and only the second
  is worth a reader's trust;
- a highlighted sentence that does not occur in the extracted proof;
- a result with no short name;
- a version history that says `proved` twice with no `invalidated` step between.

## Verdicts

| colour | meaning |
| --- | --- |
| green | as the paper states it, and it typechecks |
| red | as the paper states it, and it is refuted or open |
| blue | a repaired statement or a variant of the relation, and it typechecks |
| none | does not typecheck yet |

A refuted result keeps its red even when its repair is proved: a proved repair does not make
the printed statement true.

## Data format

[`SKILL.md`](SKILL.md) is the full specification of the data: statuses, repairs and variants,
version histories, and how to extract dependency edges from proofs rather than from numbering.
It is written as a [Claude Code](https://claude.com/claude-code) skill, so an agent formalizing
a paper can build and maintain the ledger as it goes.

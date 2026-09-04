---
name: proof-ledger
description: Build an interactive proof ledger for a paper whose metatheory is being formalized — a dependency graph of every numbered result, coloured by whether it was proved, refuted, or is still open, with each result opening our proof, the paper's proof, and the two set side by side. Use when auditing or mechanizing a paper's proofs and you want the verdicts and the dependency structure in one shareable page.
---

# Proof ledger

A paper's numbered results are ordered for reading, not for dependency — in the paper this was
built for, 73% of dependency edges cite a *higher* number, and the two adjacent propositions that
both turned out false sat in the foundations with nothing in the numbering to say so. The ledger
recovers the structure the numbering hides, and pins a verdict to each node.

## What you are producing

One page, built from one data file:

- a layered DAG of every numbered result, laid out by longest dependency path — foundations left,
  headline theorems right — each node coloured by verdict;
- a register table of the same results;
- a drawer, opened by clicking any node or row, with three tabs: **our proof**, **the paper's
  proof**, and **the two side by side**.

`assets/template.html` is the page; `assets/build.py` assembles it. Nothing in the template is
specific to a paper or a proof assistant.

```
python3 <skill>/assets/build.py build ledger.json -o ledger.html
```

Then publish `ledger.html` with the Artifact tool. Do not hand-edit the built file — edit
`ledger.json` and rebuild, or the next build silently discards your changes.

## The verdict colours

Fixed, because the distinctions are the point:

| status | meaning |
| --- | --- |
| `proved` | we prove it |
| `refuted` | we refute it **and** name the invalid step in the paper's proof |
| `conjyes` | the paper only conjectures it; we prove it |
| `conjno` | the paper only conjectures it; we refute it |
| `open` | neither proved nor refuted here |

A refutation is not `refuted` until the invalid step is identified — `build.py` refuses to build
otherwise. "The theorem is false" and "here is the line that does not follow" are different
claims, and only the second is worth a reader's trust.

Separately, `defect` on a *proved* node records a step of the paper's argument that does not hold
even though the claim does. Keep these apart. Conflating "the result is wrong" with "the proof of
a correct result is wrong" misrepresents the paper, and the second is far more common.

## Building the data

### 1. Enumerate the results

Every numbered result, including ones stated in the body and proved in an appendix. Record for
each: `ref` (`Lemma 24`), `name` (a short phrase, not the full statement), `status`, `module`, and
`defect` where there is one.

### 2. Get the dependency edges from the proofs, not from the numbering

Scan each proof for citations, bounded by the *next* result's line — an unbounded window bleeds
into the neighbouring proof and invents edges. Then read the proofs: a proof that says "by the
same reasoning as in Lemma 7" depends on Lemma 7 whether or not it names it, and a proof may lean
on a rule whose only justification is elsewhere.

### 3. Extract the paper's proofs as text

If the source is an arXiv HTML rendering, formulas survive as LaTeX in `alttext`, and:

```
python3 <skill>/assets/build.py extract paper.txt ranges.json -o proofs.json
```

de-LaTeXes them, where `ranges.json` maps each result to its `[first, last]` source lines. Read
the output before trusting it and add substitution rows for the paper's own notation. One trap is
worth knowing in advance: `\,` is a thin space that separates juxtaposed terms, so deleting it
turns `u v` into `uv` throughout.

### 4. Write our proof, and check it

`account` is prose: what our proof actually does, in two or three sentences, naming the case that
carries the argument. `sig` is the real type signature, extracted from the source rather than
retyped.

### 5. Transcribe the paper's disputed steps — and run them

This is the part that earns the page. For each faulty step, write it in the proof assistant **as
the paper writes it**, run it, and record the error verbatim. An error message names a mismatch
more precisely than prose and is checkable rather than asserted:

| the paper's step | what the checker said |
| --- | --- |
| `Ws-Lf1 e (Ws-Rfl pv)` | `u != u'` |
| `Me-App du dv` | `s != (v ∷ s)` |
| `Ws-Rgh (Ws-Rfl …) st` | `(t ↦ t') !=< (Γ ∣ [] ⊢ t ⟶ᵉ t')` |
| `Ws-Lft st d` | `Not in scope: Ws-Lft` |

Keep these in a real source file in the development, with our version live and typechecking and
the paper's commented out beside its error, so the transcription is itself under version control
and re-runnable. Never write an attempt you did not run — a fabricated error message destroys the
one thing the page is for.

Two steps resist transcription, and saying so is better than faking it: a rule application whose
*premise* is the unobtainable part (transcribe the premise's refutation instead), and a fault in
the shape of an induction over a whole proof, where no single line is what the checker rejects.

Where the paper's argument and ours coincide — usually most results — leave `agda` unset. The page
says the two coincide rather than manufacturing a contrast.

## Data shape

```jsonc
{
  "meta": { "title": "…",        // 2–4 word artifact name
            "eyebrow": "…",      // authors · venue · identifier
            "headline": "…", "standfirst": "…",   // HTML allowed
            "footer": ["…"] },
  "nodes": [ { "id": 24, "ref": "Lemma 24", "name": "narrowing a promotion",
               "status": "proved", "module": "MPSS.CoNarrow",
               "defect": "wf conclusion argued by an induction that would prove every term wf" } ],
  "deps":  { "24": [19, 25, 12] },        // result -> the results its proof cites
  "detail": {
    "24": {
      "module": "MPSS.CoNarrow",
      "account": "…",                      // HTML allowed
      "sig": "Lem-24 : ∀ (Δ : Ctx) …",
      "paper": ["line", "line"],           // from `extract`
      "faults": [ { "q": "verbatim sentence from `paper`", "note": "why it fails" } ],
      "agda": { "quote": "…", "paper": "…", "err": "…", "ours": "…", "note": "…" }
    }
  }
}
```

**Which fields take markup.** `meta.headline`, `meta.standfirst`, `account`, `faults[].note` and
`agda.note` are rendered as HTML, so `<code>`, `<em>` and `<br>` work in them and are worth using —
a note that names a rule reads far better with the rule in code. Everything else is inserted as
text and will show its tags literally: `name`, `defect`, `sig`, `agda.quote`, `agda.paper`,
`agda.ours`, `agda.err`, and the extracted `paper` lines. That asymmetry is deliberate — the
paper's text and the proof assistant's output must never be interpreted as markup — but it is easy
to forget when writing a note, so check a note containing tags in the built page before publishing.

`faults[].q` must appear verbatim in that result's `paper` lines — the page highlights it in
place, and `build.py` refuses to build if a quote does not match. That check is the guard against
marking a sentence the paper never wrote.

## What `build.py build` refuses

- a dependency on a result that is not in `nodes`;
- a `faults` quote that does not occur in the extracted proof;
- a node marked `refuted` with no invalid step named.

## Tone

The page is an audit, and it is read by people who may include the authors. Report what was
checked. Where a claim stands and only its argument fails, say exactly that. Where an earlier
finding turns out to be wrong, withdraw it in the page rather than quietly dropping it — the
`account` and `defect` fields are the right place, and a withdrawn criticism is information too.

## Notes from a second paper

The skill was written from one paper and then run on a second — an earlier version of the same
calculus. Three things it got wrong, now fixed, and worth knowing because they recur:

- **Result ids are labels, not numbers.** The second paper numbers by `section.result` (`4.3`),
  not `17`. Ids are opaque strings throughout; `ref` carries what the reader sees, and column
  order follows declaration order rather than a numeric sort.
- **`\;` in a substitution pattern matches a bare semicolon.** It ate every `Γ;s` separator. Write
  `\;` for LaTeX's thick space, and check a sample containing the paper's own punctuation before
  trusting a batch extraction.
- **Citation scanning under-counts.** A regex over the proof text missed dependencies that a
  substring check found, so treat the scan as a first pass and read the proofs — which the skill
  already says, and which the run confirmed the hard way.

The run also produced a finding, which is the argument for doing it at all: the same uncited step
appeared in both versions. Both preservation theorems move from `t ↦ t′` to `t ⟶≡ t′` without
citing the proposition that bridges them. In the first paper that proposition is true and the gap
is cosmetic; in the second it is refuted and the gap is fatal. Auditing the ancestor located the
defect's origin.

## Notation

Render the paper's symbols, not its macro names: `\mathsf{Top}` is `⊤`, and a reader following a
proof wants the symbol. Keep the distinction sharp in three places:

- **math mode in the paper's text** — convert;
- **the paper's own prose** ("Theorem 11, No supertype of Top") — leave, it is their sentence;
- **identifiers of the proof assistant** (`Ms-Top`, `Wf-Top`, `Top≰lam`, and anything in a `sig`
  or an `agda` block) — leave, or the page misreports what the source says.

A guard of the shape `(?<![-\w])Top(?![-\w≰≉⟶])` separates the term from the rule names that
merely contain it, so the substitution can be applied to prose and inline code alike without
touching `Me-Top`. Whatever symbol you convert, add it to the spacing character classes too, or
it comes out welded to the operators around it — `⊢⊤≤*` rather than `⊢ ⊤ ≤*`.

## The side-by-side must show the verdict, not a repair

On a `refuted` node the right-hand column is our **refutation** — the term inhabiting `¬ P`. It is
not the step that would have worked. The distinction is easy to lose, because the natural thing to
write beside a rejected step is the corrected step, and a corrected step typechecks; a reader then
sees a positive proof under a red node and reasonably concludes the page contradicts itself.

Keep the two apart. The left column says why the *proof* fails; the right says why the *statement*
does. Where a repaired form exists and is proved, put it in the note, and say that it repairs the
statement rather than establishing it. The template captions the column from the node's status for
the same reason — "Ours — the refutation" under a refuted result, never "accepted".

## Starting from a paper with nothing mechanized

Omit `--agda` and the ledger is derived from the paper alone: every numbered result, its statement
and proof, and the citation graph, with everything open. That ledger is worth having on its own —
it is the paper's structure, which its numbering hides — and it is the input to the scaffold:

```
derive.py   --paper paper.txt --title "…" -o ledger.json
scaffold.py --ledger ledger.json --out src/Paper --prefix Paper
agda src/Paper/All.lagda.md
```

One module per result, each carrying the paper's own statement and importing the modules for the
results its proof cites — **so the paper's citation graph becomes the import graph**, and Agda
enforces from the first day that the formalization respects it. The skeleton typechecks as
emitted, every module empty but for its imports, so results can be filled in one at a time and in
any order. Re-running leaves existing modules alone unless `--force`.

**No types are generated.** Turning an informal statement into a type is the work, and a
plausible-looking guess is worse than none because it invites you to accept it. What is emitted is
the statement, verbatim, as the specification to translate.

Expect the import graph to be thinner than the truth. The citation scan finds what a proof names,
and a proof that says "by commutativity and the diamond property" names nothing; add the missing
edges through the annotations overlay as you discover them, and the next scaffold picks them up.

## Derive first, annotate second

Do not hand-write a ledger. Derive the skeleton from the sources, then lay judgements over it, so
that a re-derivation refreshes every fact without disturbing a written word.

```
derive.py --paper paper.txt --agda MPSS --map map.json -o skeleton.json
build.py  build skeleton.json --annotations annotations.json -o ledger.html
```

**What `derive.py` reads off the sources**, none of it a judgement:

- the numbered results, from the paper's own headers, and each one's statement and proof text;
- which of them the development proves, by matching each result to a definition — `Lemma 24` to
  `Lem-24`, `Theorem 3` to `Thm-3`, a dotted number to `Lem-5·3` — with `--map` for the ones that
  do not follow the convention;
- **what each proof rests on**, two ways: the results the paper's proof cites, and the results our
  definition's body actually mentions;
- **which proofs are conditional**, by reading the enclosing `module _ (h : H) where` parameters
  and keeping those whose type is a declared statement, discarding scoping side conditions.

**What belongs in the annotations**, because none of it can be read off: the short name, the prose
account, the sentence a fault sits on and why it fails, a transcribed step, and any verdict that
should read differently from what the derivation infers.

### Three distinctions the derivation has to get right

- **A statement is not a proof of itself.** `Lem-1 : Set` in an assumptions module *declares* the
  statement; it is not a proof. Classify a bare `: Set` as open, and where both a statement and a
  proof carry the same name, let the proof win.
- **A `¬` in a type proves nothing about the paper.** Plenty of true theorems are negative — "no
  supertype of `⊤`" is one — and plenty of proofs take a negation as a *hypothesis*. Whether our
  statement contradicts the paper's is not visible in the type. Pin refutations by naming
  convention (`…-false`) or `--map`.
- **Status and hypotheses are orthogonal.** Status answers "is there a proof of this here";
  the hypothesis list answers "what does it rest on". Do not propagate openness along hypotheses:
  it whitens most of a conditional development and erases the difference between having no proof
  and having a conditional one. Pin the verdict in the annotations where it should read otherwise.

### The analysis is lexical, and that is its real limitation

Agda publishes no definition-level dependency information. `--dependency-graph` is module-level;
`--interaction-json` is a stateful editor protocol; `.agdai` is undocumented binary. So a
definition's dependencies are found by scanning its body for names, which cannot tell a reference
from a coincidence of spelling.

What makes that tolerable is a filter, not a fix: a reference is only possible if the referring
module can actually see the referenced one, so every lexical edge is checked against the transitive
`open import` graph and dropped when nothing backs it. On the development this was built from the
filter dropped nothing, which says the names were distinctive there — not that the scan is sound in
general. Read the reported edges before trusting them, the same as the citation scan.

### What it will tell you about the paper

A derivation that reports its own confusion is doing its job. Expect it to find results it cannot
match to a definition — some are naming, some are genuinely unmechanized — and mutual recursion in
the development, which appears as a cycle and has one edge dropped per cycle so the layout stays a
DAG. On the paper this skill was built from it also reported that **Lemma 1 is restated as
"Theorem 1" in the appendix**, which nobody had noticed by reading.

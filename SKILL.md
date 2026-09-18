---
name: proof-ledger
description: Build an interactive proof ledger for a paper whose metatheory is being formalized — a dependency graph of every numbered result, coloured by whether it was proved, refuted, or is still open, with each result opening its version history — how it was reached, with any two versions side by side — and the paper's proof. Use when auditing or mechanizing a paper's proofs and you want the verdicts and the dependency structure in one shareable page.
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
- a drawer, opened by clicking any node or row, with three tabs: **how it was reached** — the
  version history, newest at the top and expanded with the definition as it stands, each earlier
  step collapsible with the definition it had, the paper's original at the bottom (its printed
  statement as text, its Agda transcription as the definition), and two selectors that put any
  two versions side by side in a panel centred on the screen — aligned as a diff, modulo the
  primes a variant puts on names, when the two share a signature: a repair, or a datatype's
  variant — and **the paper's proof**, with the
  disputed step transcribed and the checker's verdict on it. Datatypes and functions open to the
  same history with one tab.

`assets/template.html` is the page; `assets/build.py` assembles it. Nothing in the template is
specific to a paper or a proof assistant.

```
python3 <skill>/assets/build.py build ledger.json -o ledger.html
```

Then publish `ledger.html` with the Artifact tool. Do not hand-edit the built file — edit
`ledger.json` and rebuild, or the next build silently discards your changes.

## The verdict colours

The data records a *status* per result; the page derives a *colour* from the status and the
repair, and applies the same colours to datatypes and functions:

| colour | meaning |
| --- | --- |
| green | as the paper states it, written in Agda, and it typechecks — a proved result; a faithful datatype or function |
| red | as the paper states it, and it does not hold — `!` refuted, `?` open, plain for a definition that does not typecheck |
| blue | edited — a repaired statement, or a variant of the relation — and it typechecks; the `!` or `?` still says what the original was |
| none | does not typecheck yet — a conjecture of the paper's, which made no claim, or an edit still in progress |

Datatypes and functions are green by default, since the tree typechecks and the encoding is
audited for fidelity. A datatype whose name is another's plus a prime (`_∣_⊢_⟶ᵉ′_` beside
`_∣_⊢_⟶ᵉ_`) is read as an edited form of it and shown blue, with the original named on its
card; pin other exceptions in `meta.fidelity` as `{"T:name": "edited" | "fails" | "editing"}`
(`F:` for a function) — a relation invented for a repair, say. The edited datatypes reach the
graph through the variant definitions: a map entry whose key carries a trailing prime,
`"2′": ["Lem-2′"]`, names the repaired or variant definition of result 2, and the datatypes and
functions in *its* statement are added to the result's, marked "in the repaired form". The statuses themselves are fixed, because the distinctions
are the point:

| status | meaning |
| --- | --- |
| `proved` | we prove it |
| `refuted` | we refute it **and** name the invalid step in the paper's proof |
| `open` | neither proved nor refuted here |

A conjecture of the paper's is simply `open` until it is settled, and then `proved` or `refuted`
like anything else; the tally still counts the paper's own conjectures apart from its claims, by
reading the `ref`. (Two earlier states, `conjyes` and `conjno`, are retired; `build.py` refuses
them.)

**Repairs and variants.** A refuted or open result often has a second life: a repaired statement
(Proposition 18 with the scoping premise), or a variant of the relation it is about (the diamond
for a reduction with one premise moved). Record that on the node as `repair` (short text: what
the repaired form or variant is, and where), `repairKind` (`repaired` or `variant`, by the same rule: a repair keeps the signature, a variant changes it) and
`repairStatus` (`proved`, `assumed`, `refuted` or `open` — the verdict on the repaired form, not
on the original). The page marks such a node ↻ in the graph, coloured by `repairStatus`, adds a
register column, and shows it in the drawer. The node's own `status` stays what it is: a proved
repair does not make the printed statement true.

**The steps it took.** A repair, a variant, or a proof that had to route around a defect in the
paper's argument is rarely the first thing tried, and the failed attempts are what a later reader
most needs — otherwise they are re-derived. Record them on the node as `attempts`, in order, one
entry per attempt: `what` (the idea, in a sentence), `outcome` — one of exactly five,
`proved`, `refuted`, `open`, `experiment` or `invalidated`; an assumption, an abandoned route, a
conditional proof and a proof of only part of the statement are all `open`, a withdrawn claim is
`refuted`, a search, probe or sweep that gathers evidence without settling anything is an
`experiment`, and `invalidated` is described below; for a datatype or function the
statuses are `checked` and `rejected` instead, since a definition either typechecks or does not
— `kind` — one of exactly three, `original` (as the paper
has it), `repair` (the signature kept, the body changed: another proof of the same statement, a
datatype with the same header and a changed rule) or `variant` (the signature changed: a
premise added, a relation replaced; an edited datatype is always a variant, since a declaration
has no body apart from its rules) — `because` (what motivated trying this, in a sentence: the
finding, the citation or the failure that led here; required, since a step without its
motivation is a step someone will repeat) — `change` (the id of the change this step is part
of, declared once in the top-level `changes` list as `{id, when, title, summary}`) — `where` (the module,
probe or catalogue row that preserves it — a failure preserved only as prose is a failure someone
will repeat), and `why` (what killed it, or what it gave). Order is information: the list is a
sequence, and the page numbers it. Put it on any node that has a `repair`, and on a proved node
whose `defect` was fixed by a different argument from the paper's; the last entry is the one
that stands, and the page gives it the final definition. An entry may carry `def`, the Agda text
of the definition at that step (a declared statement, a refutation's type, a variant's
signature), which is what the side-by-side comparison shows; extract it from the source rather than
retyping it. Steps without a `def` say so and name their `where`.

**A log is the history of one statement, so it says `proved` once.** `proved` on a step means the
node's statement — or its declared repair or variant — is proved, not that some piece of work
typechecked. A proved statement is revisited for two reasons only: a lemma under it is
invalidated, or a result above it needs it in another shape. The log then carries an
`invalidated` step between the two — `what` fell, `why`, and in `change` the id of the change that
did it, which the page prints as "invalidated by" and the change's title — and the next attempt
follows. `build.py` refuses a step that follows a `proved` (or, for a definition, a `checked`)
with no `invalidated` between them; an `experiment` may come anywhere. Three things look like a
second `proved` and are not steps of this log:

- *a supporting lemma* proved on the way — it is a node of its own. Name it in the map under
  `development`, `{"id": "8a", "ref": "Lemma 8a", "names": ["FunCongr"], "supports": ["8"]}`, and
  `derive.py` makes it a result with `origin: development`, an edge from each result it supports,
  no paper tab, and no place in the tally of the paper's claims;
- *the pieces of one result* — three forms of a substitution lemma, two of three conclusions —
  are one entry whose `where` lists every module; until the last piece is in, the entry is `open`;
- *a consequence* — a theorem transferred, the consumers re-derived — belongs in the log of the
  result it is about.

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
  "meta": { …, "notes": { "title": "What remains", "items": [ { "anchor": "…", "html": "<p>…</p>" } ] },
            "legendLede": "…", "registerLede": "…",     // optional; the page computes them otherwise
            "aliases": { "⟶≡": "T:_∣_⊢_⟶ᵉ_" } },       // the paper's notation -> a card
  "nodes": [ { "id": 24, "ref": "Lemma 24", "name": "narrowing a promotion",
               "status": "proved", "module": "MPSS.CoNarrow",
               "defect": "wf conclusion argued by an induction that would prove every term wf" },
             { "id": 18, "ref": "Proposition 18", "name": "reflexivity", "status": "refuted", …,
               "repair": "reflexivity with the scoping premise, MPSS.StackPush",
               "repairKind": "repaired", "repairStatus": "proved",
               "attempts": [ { "what": "…", "outcome": "refuted", "where": "MPSS.ReflFails", "why": "…" },
                             { "what": "…", "outcome": "proved",  "where": "MPSS.StackPush" } ] } ],
  "deps":  { "24": [19, 25, 12] },        // result -> the results its proof cites
  "detail": {
    "24": {
      "module": "MPSS.CoNarrow",
      "account": "…",                      // HTML allowed
      "sig": "Lem-24 : ∀ (Δ : Ctx) …",
      "types": [ { "name": "_∣_⊢_⟶ˢ_", "module": "MPSS.Reduction", "decl": "data … where …" } ],  // derived
      "paper": ["line", "line"],           // from `extract`
      "faults": [ { "q": "verbatim sentence from `paper`", "note": "why it fails" } ],
      "agda": { "quote": "…", "paper": "…", "err": "…", "ours": "…", "note": "…" }
    }
  }
}
```

**Which fields take markup.** `meta.headline`, `meta.standfirst`, `meta.notes[].html`, `account`, `faults[].note` and
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
- a node marked `refuted` with no invalid step named;
- a step that follows a `proved` or `checked` step with no `invalidated` step between them, or
  an `invalidated` step that names no change.

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

## The transcribed step must show the verdict, not a repair

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

- **what each statement is built from**: every `data` and `record` declaration of the
  development whose name the statement's type mentions (a mixfix name by its pieces, in order,
  within one arrow-segment), looking through abbreviations — a definition of type `… → Set`
  such as `Γ ⊢ u ≋wf t = Γ ⊢ u ⊑wf[ eqv-m ] t` counts as a mention of what it unfolds to —
  filtered by what the statement's module can see, and carried with
  its declaration so the card shows the constructors. Modules the development imports from
  beside its root — a shared syntax module — are read too. `types` in `detail` lists them per
  result; `types` and `typedeps` at the top level make them **nodes of the dependency graph**, layered
  by longest path with the results, with an edge from each result to the types in its statement and from each
  type to the types its declaration mentions. A type node opens to its declaration and the
  results that use it. Datatypes are pill-shaped and their edges dashed, so the reader can tell
  "rests on this relation" from "cites this lemma". A mixfix name is shown readably, each `_`
  filled from the declaration's index types (`Ctx` → `Γ`, `Stack` → `s`, `Tm` → `t`, `t′`, …):
  `_∣_⊢_⟶ᵉ_` reads `Γ ∣ s ⊢ t ⟶ᵉ t′`; the raw name stays in the card's eyebrow.
- **the functions** those statements and datatypes are built from — opening, substitution,
  free variables, the domain of a context, judgement abbreviations: any definition whose
  type's target is a plain type (a term, a context, a list, `Set`) rather than a proposition,
  mentioned in a statement, a declaration or another function's definition; constructors,
  local helpers and the definitions that stand for numbered results are excluded. `functions`
  at the top level; square nodes in the graph, each opening to its type and clauses. Type
  synonyms (`Ctx : Set`, `Ctx = List …`) count as datatypes. Modules imported from beside the
  root are indexed for all of this, but a numbered result never matches a definition there.

**Every mention links.** Inside a card, a numbered result ("Lemma 24"), a datatype (by its full
name, or by the one piece of a mixfix name that is rarest across the declarations — `⟶ᵉ`, `⊲`,
`↣`), and any constructor or field of a datatype (`Me-Pro`, `Ws-Rgh`, `Pv-Sta`) becomes a link to
that card, in prose, in the paper's text and inside the Agda blocks alike; a constructor link
opens the datatype with that constructor's lines highlighted. The paper's own notation is not
derivable, so map it in `meta.aliases`: `{ "⟶≡": "T:_∣_⊢_⟶ᵉ_", "Os-Bet": "T:_↦_#E-App" }` —
a token to a result id, a type id, or `type id#constructor`. Datatype ids are `T:` plus the name.
A name that is also an ordinary lowercase word (`step`, `plug`) links only where it appears in
code, so prose is not littered. Edited datatypes and functions carry, in `types` / `functions`
of the annotations keyed by id, an `account` and `attempts` like a result's, and an `original`
note on the paper's declaration; the page adds the paper's original as the bottom entry itself
(dotted circle), so do not record it as a step. A result with a variant shows the variant's Agda
statement beside the original. Hovering any link shows a card with the signature behind the name — a result's Agda type, a
datatype's header, or the constructor's own lines — so a reader can check a rule without leaving
the proof they are in.

- **what is defined together**: the strongly connected components of the development's own
  reference graph — results whose definitions call each other, judgements declared in one
  mutual block, functions defined together. `groups` at the top level; the page draws each as
  one supercard, its members stacked in a single column at the layer of the deepest of them.
  The paper's citation cycles are not groups: only the development's edges count.

**The log of changes.** A change usually touches several cards — a relation edited, the
diamond proved for it, commutation proved for it, a theorem transferred. Declare each change once
in `changes` and tag every step that belongs to it with its id; the page then links those steps
to each other across cards ("part of …, with …") and renders a log section listing every change
in date order with its steps grouped. The build refuses a step whose change is undeclared.

**Fidelity, rule by rule.** A transcription is faithful only if each constructor of each
datatype the paper defines matches one of its rules, and the differences the encoding forces are
named. Record that on the datatype in the annotations: `origin` (`paper`, `encoding` for an
artefact such as local closure or a mode index, or `development` for something the paper does
not have), `fidelity` (a sentence on the datatype as a whole) and `rules`, a map from
constructor to `{rule, note}` — the paper's rule name and where the two differ (a cofinite
family for "x fresh", a side condition added, a base case the paper leaves implicit). The build
refuses a paper datatype with a constructor left unnamed, and the card shows the table beside
the declaration, so a reviewer checks every rule against the paper in one pass.

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

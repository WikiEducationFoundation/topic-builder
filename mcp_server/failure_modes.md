# Failure modes

A catalog of named anti-patterns observed across topic builds: what
goes wrong, how to recognize it, and what to do about it. Each entry
is grounded in at least one observed dogfood case.

These are *strategy* anti-patterns, distinct from the *tool-API*
quirks documented in `server_instructions.md`'s KNOWN SHARP EDGES
section. A sharp edge is "this tool's wrapper has a non-obvious
behavior" (e.g., compound `intitle:` operators silently return 0).
A failure mode is "this combination of topic-shape + tool-choice
produces a recurring bad outcome" (e.g., morelike: from a polymath
biography returns profession-peers, not topic-peers). The two
catalogs are complementary; consult both.

## How to use this catalog

- When a strategy underperforms or produces surprising output, scan
  the `detection` cues here for a match before assuming the topic
  is just hard.
- The `rescue` field points to either a fix (specific tool sequence)
  or a move from `mcp_server/strategy_moves.md` that addresses the
  pattern.
- Many failure modes are detectable from observable signals
  (`describe_topic` output, `resolve_redirects` collapse rate,
  source-overlap percentages). Ship 2's `audit_progress` will scan
  these automatically.

## This catalog is a starting point, not a closed enum

If you encounter an anti-pattern that isn't listed here, name it in
`submit_feedback.strategy_execution.failure_modes_observed` so we
can grow the catalog. New failure modes are evidence that we're
seeing topic shapes the catalog hasn't anticipated.

## Schema

```
failure-mode: <name-with-hyphens>
symptom:      <what you observe>
detection:    <how to recognize it>
rescue:       <what to do; may point to a move>
evidence:     <session or exemplar where it was observed>
```

---

# Topic-shape / Wikipedia-modeling anti-patterns

You misread the topic, or Wikipedia models it differently than
expected, and a default strategy doesn't fit.

## topic-is-subtype-of-parent

```
symptom:    no Category:<topic>; only Category:<parent-class>; the
              topic is encoded as a Wikipedia article + scattered
              sub-articles, not as a category subtree
detection:  survey_categories(<topic name>) returns nothing or
              returns only a redirect / container / sparse stub;
              survey on the parent (Diabetes, Motor Neuron Disease,
              autism spectrum) returns a populated tree
rescue:     pull parent + filter by Wikidata property join (P780
              symptoms, P2293 genetic association, P2176 drug used
              for treatment for diseases) — annotate, don't filter.
              See move: wikidata-property-probe-additive.
            Accept that recall on the subtype is bounded by the
              parent's coverage and the AI's per-article inclusion
              judgment.
evidence:   2026-04-25 Type 2 diabetes (no Category:Type 2 diabetes;
              only Category:Diabetes)
```

## adversarial-categories-under-topic-root

```
symptom:    subcats explicitly opposed-to or competitive-with the
              topic appear under the canonical category root (Salafi
              and Wahhabi inside Sufism; "Anti-X" categories;
              critics-of-the-topic categories)
detection:  survey_categories shows subcats whose names contradict
              the topic
rescue:     enumerate at survey time; pass exclude=[adversarial
              subcat names] before pulling get_category_articles.
              See move: branch-excluded-category-sweep.
evidence:   2026-04-25 Sufism (Salafi, Wahhabi, Anti-Sufism all
              direct subcats of Category:Sufism)
```

## consolidation-into-list-pages

```
symptom:    individual instance articles (characters, songs, scenes,
              episodes) redirect into "List of <topic> characters" /
              "<topic> discography" parent articles, suppressing
              instance-level recall
detection:  resolve_redirects sample shows many redirects of the
              shape "<minor-name>" → "List of <topic> characters";
              corpus is much smaller than expected for a culturally
              rich topic
rescue:     accept the consolidation as a hard recall ceiling for
              instance-level coverage; harvest the consolidating
              list pages directly (treat them as canonical instance
              enumerations).
            For oeuvre topics, also pursue per-work navboxes
              (Template:<film>, Template:<album>) to capture the
              instances Wikipedia did keep separate.
evidence:   2026-04-25 Studio Ghibli (Kurotowa, Asbel, Ohmu and other
              Nausicaä characters all redirect to "List of Nausicaä
              of the Valley of the Wind characters")
```

## container-category-empty

```
symptom:    survey_categories(<existing category>) returns 0 articles
              despite the category clearly existing; or category
              page is a redirect / container with no direct members
detection:  survey returns total_articles=0 with no error; the
              category page on Wikipedia has children but no direct
              articles
rescue:     scan for sibling categories with the canonical name
              (e.g., Category:Korean television dramas is a
              container; the real one is Category:South Korean
              television series). Try plural / nationality variants.
              Future: a "soft-redirect category hint" tool surface.
evidence:   2026-04-23 K-drama session (Korean television dramas
              container)
```

---

# Source-trust failures

You trusted a source that wasn't really topic-aligned, and the
resulting pull contaminated the corpus.

## wp-broader-than-topic

```
symptom:    a relevant WikiProject exists and tags many articles,
              but covers a superset of the topic; pulling it adds
              30–50% out-of-scope material
detection:  WP article count >>> topic-relevant scope; sample of
              recently-pulled WP titles shows many cross-discipline
              or cross-region articles
rescue:     wp-intersect-category move (intersect with a topic-
              specific category) instead of pulling outright;
              OR skip the WP entirely if no canonical category
              exists.
            Future: count_wikiproject_articles reconnaissance to
              size the WP before committing.
evidence:   2026-04-25 London Underground (WP London Transport
              covers buses, river services, Overground, DLR);
              2026-04-24 Vietnam War (WP Military History tags
              hundreds of thousands of articles)
```

## wp-registered-but-empty

```
symptom:    find_wikiprojects shows a WP exists; check_wikiproject
              confirms its template namespace exists; but
              get_wikiproject_articles returns 0 articles
detection:  WP article count = 0 despite existence
rescue:     skip; rely on category + list-page + search. The WP is
              dormant despite registration.
            Capture in feedback so the catalog and any
              wikiproject-recon move learn that this WP is
              registered-but-inactive.
evidence:   2026-04-25 Esperanto (WikiProject Esperanto registered;
              tags zero articles)
```

## genre-bleed-via-full-discography

```
symptom:    a musical-genre topic includes acts whose primary genre
              isn't this one; depth-3 sweep folds in their full
              discographies (Mumford & Sons albums under Bluegrass,
              The Chicks albums under Bluegrass)
detection:  resolve_redirects collapses many song→album redirects
              for non-core acts; describe_topic top-first-words
              dominated by adjacent-genre artists; per-act
              album/song subcats appear under the genre category
              root for acts that aren't primarily of this genre
rescue:     post-pull, run remove_by_source on the per-act album
              subcats; OR Wikidata P136 (genre) join — keep only
              articles whose primary genre is the topic.
            Pre-pull, exclude full-discography subcats of borderline
              acts in the branch-excluded sweep.
evidence:   2026-04-25 Bluegrass (Mumford & Sons, Dixie Chicks /
              The Chicks)
```

## fictional-X-bleeds-under-real-X-root

```
symptom:    a real-world topic's category root contains "Films set
              on X", "Novels set on X", "Works about X",
              "X in popular culture", and these subcats fold in
              fictional characters / settings / storylines
detection:  survey_categories shows fiction-flavored subcats; corpus
              after pull contains entries like "Cordell Walker"
              (Walker Texas Ranger character) under Vietnam War,
              "Andrew Chord" (Marvel character) under Vietnam War
rescue:     enumerate fiction-flavored subcats at survey time and
              pass to exclude=[...]; OR accept them and post-prune.
            Pattern-based exclude (Ship 2 candidate) would catch
              "fiction about X" / "set on X" / "popular culture"
              variants generically.
evidence:   2026-04-25 Vietnam War (Marvel characters, Walker Texas
              Ranger redirects under Vietnam War subtree); Chernobyl
              (S.T.A.L.K.E.R. game franchise excluded successfully
              by manual judgment)
```

## main-article-context-link-noise

```
symptom:    harvest_list_page on the topic's main article adds many
              context links rather than topic-member articles
              (physics articles, geographic places, generic
              concepts) — especially severe on single-event topics
detection:  source_label list_page:<topic-main-article> shows a
              high ratio of newly-added titles, but a sample reveals
              tangential context articles, not topic-defining ones
rescue:     for single-event topics, prefer parent-program-navbox
              over main-article harvest if available; otherwise
              run description-fetch-then-pattern-clean to bulk-clear
              context-link noise after the pull.
            See move: main-article-as-list-page (the warning is in
              the move entry).
evidence:   2026-04-25 Chernobyl (main-article harvest brought in
              Iodine-135, Zircaloy, Neutron poison, Electrical
              engineering, generic Soviet politicians)
```

## list-page-prose-contamination

```
symptom:    harvest_list_page with main_content_only=True still
              brings in non-list-member articles via prose links in
              the page intro / between-section running text
detection:  list-page source contributes a noticeable fraction of
              false positives in spot-check; titles look like
              concepts or organizations referenced in body prose,
              not list members
rescue:     post-pull, review the source's contributions via
              get_articles_by_source(<list-page>,
              exclude_sources=[other sources]) and apply
              remove_by_pattern or auto_score_by_description.
            Future: an "enumerated section only" mode on
              harvest_list_page (extract links inside <ul>/<ol>/
              table rows; ignore links in <p>).
evidence:   2026-04-24 thin-variant cycle — 3 of 5 topics named this
              (AA-STEM, HL-STEM, orchids regional lists)
```

## popular-culture-list-page-overlinking

```
symptom:    harvest_list_page on a "<topic> in popular culture"
              article adds many tangential entities (broadcasters
              that aired the event, countries that observed it,
              eponymous works using the topic's catchphrases,
              generic concepts referenced once) — not items
              culturally derived from the topic.
detection:  source_label list_page:<topic> in popular culture
              shows a high contribution count where a sample of
              titles is dominated by network / country / concept
              articles rather than works or named-after items.
              Hallmark surface vocabulary in the sample: TV
              networks, country names, words like "Public domain",
              "Voice-over", generic professions.
rescue:     pre-call: use preview_harvest_list_page first; eyeball
              a 30-title sample. If the sample is dominated by
              tangential entities, skip the bulk harvest. Reach
              for compound intitle: probes on the topic's named
              catchphrases instead — those return eponymous
              candidates that need filtering, but at lower bulk
              noise.
            post-call (if you already harvested): describe the
              source label and apply remove_by_pattern with a
              network/country regex; or filter by description-
              type to drop generic-concept articles.
            general rule: any "<topic> in popular culture" or "List
              of cultural references to <topic>" candidate gets a
              preview, not a commit. Same shape applies to "List of
              <topic>-themed works" pages.
evidence:   2026-04-26 apollo-11 phase-2 — harvest_list_page on
              "Apollo 11 in popular culture" added 148 articles;
              the audit then judged ~95% of the new titles OUT
              (broadcasters, countries, eponymous works that aren't
              about A11). Drove the run's precision from 0.55 to
              0.30 in one call.
```

---

# Identity / collision failures

Tool sequence pulled the wrong article into the corpus because of a
naming collision.

## eponym-collisions-on-instance-lists

```
symptom:    instance-enumeration list pages (taxonomy genus species
              lists, sports rosters) include biographies of people
              whose surname matches an instance epithet
detection:  list-page contributions include biographies whose subject
              isn't of the topic-class; the surname matches a known
              taxonomic epithet or instance name
rescue:     sample-verify list pages before bulk harvest; for
              taxonomic lists specifically, future
              annotate_types=True flag will tag person-vs-plant.
            Today: harvest, then describe_topic + remove_by_pattern
              with profession descriptors (botanist, ornithologist)
              that catch the human contaminants.
evidence:   orchids exemplar (Dendrobium species list leaks
              biographies named "Smith", "Robinson", etc.)
```

## ambiguous-namesake-collision

```
symptom:    a search or list-page harvest pulls in a person whose
              name matches a topic-relevant figure but who is a
              different person entirely (Walter Robinson the
              Pulitzer winner vs Walter V. Robinson the journalist;
              two Oakes Ameses — orchid taxonomist and 19th-century
              politician)
detection:  spot-check fails on a famous name with verifiable
              attributes (publication dates, institutional
              affiliations); the article in corpus doesn't match the
              expected biographical facts
rescue:     fetch_article_leads on the title to disambiguate;
              reject the wrong one with reason="namesake collision"
              and add the right one manually.
            For taxonomic topics where eponym collisions are
              foreseeable, set sticky rejections preemptively before
              the relevant gather.
evidence:   2026-04-23 Pulitzer session (multiple namesake
              collisions); orchids exemplar (Oakes Ames)
```

## profession-axis-implicit-leak

```
symptom:    auto_score_by_description with required_any axes rejects
              genuine intersectional biographies because the
              shortdesc elides the demographic axis ("American
              neuroscientist" doesn't say "Mexican-American
              neuroscientist")
detection:  auto_score_by_description dry-run breakdown_by_reason
              shows large clusters of rejections whose shortdesc
              looks topic-relevant on profession alone; the implicit
              axis is the one missing
rescue:     re-run with required_any={} (disqualifying-only); or
              keep only the profession axis required, not the
              demographic axis. See server_instructions.md
              INTERSECTIONAL TOPICS guidance.
            shortdesc-ambiguity-disambiguation on the affected
              candidates.
evidence:   server_instructions.md notes; 2026-04-23 AA-STEM /
              HL-STEM pattern
```

---

# Tool-misuse patterns

The tool was used outside its safe envelope.

## wikidata-property-used-as-subtractive-filter

```
symptom:    a Wikidata property probe, intended to find candidates,
              gets misused to *exclude* articles whose property
              isn't set ("only keep items with P171=Orchidaceae")
detection:  silent drops after a Wikidata join; the "drops" are
              real on-topic articles whose property simply wasn't
              tagged on Wikidata yet
rescue:     never use Wikidata properties as subtractive filters.
              Probe additively only — surface candidates, then let
              the AI judge inclusion. See server_instructions.md
              ADDITIVE vs SUBTRACTIVE.
            If a Wikidata-as-filter operation already happened,
              re-pull the source candidates and review the dropped
              set against the rubric.
evidence:   orchids exemplar (P31 / P171 used-as-filter would have
              dropped hundreds of real species)
```

## morelike-from-polymath-seed

```
symptom:    search_similar / preview_similar from a biographical
              seed returns ~50% off-topic — profession-peers,
              tangential collaborators, unrelated filmography
detection:  preview_similar limit=20 shows the seed's
              cross-discipline edges dominate the results; the seed
              is a person known across many fields, or a politically
              prominent figure, or a novel whose adaptation has its
              own strong edge graph
rescue:     revert via remove_by_source("search:morelike:<seed>")
              if already committed; reseed from a *concept, event,
              or work* rather than a person.
            See move: morelike-from-pure-topic-seed (the warning is
              in the move entry).
evidence:   server_instructions.md NOISE TAXONOMY; HL-STEM session
              (morelike from a Hispanic chemist returned
              non-Hispanic chemists)
```

---

# Workflow / state failures

The corpus state or the workflow's stickiness produced a recurring
problem.

## heritage-redirect-mass

```
symptom:    >10% of the corpus collapses on resolve_redirects,
              dominated by historical / abandoned-project /
              renamed-entity titles
detection:  resolve_redirects collapse rate >10% (London
              Underground: 34%); redirect samples show abandoned-
              project names, era-specific titles, transliteration
              variants
rescue:     run resolve_redirects EARLY in the build (before WP /
              list pulls that may rediscover the same canonicals);
              treat the inflated source counts pre-resolve as
              expected, not as a recall signal.
            See move: redirect-resolution-pass.
evidence:   2026-04-25 London Underground (914 / 2700 = 34%)
```

## lossy-redirect-target-meaning-divergence

```
symptom:    resolve_redirects merges a title into a target whose
              semantic identity differs from the source's — bio
              merged into event/work, building merged into city,
              building merged into different-building, organization
              merged into parent-project, etc.
detection:  redirect samples show shape changes — bio → event
              ("Howard Levy (U.S. Army officer)" → "Court-martial of
              Howard Levy"); building → city ("Portsmouth Central
              Library" → "Portsmouth"); building → different-building
              ("Carradale House" → "Balfron Tower"); organization →
              parent project — where the canonical's meaning differs
              from the source's
rescue:     review redirect samples before committing on topics
              where source-vs-target divergence has scope-relevant
              consequences (biographical-density=high; shape is
              instance-enumeration like buildings or works); for
              surprising merges, manually re-add the source-typed
              article under
              source="manual:restore-after-lossy-redirect" so the
              audit trail is self-describing.
            Future: a "lossy-redirect detection" guardrail when
              source/target QIDs differ meaningfully (different P31,
              or different parent-class chain).
evidence:   2026-04-24 AA-STEM cycle (bio → event); 2026-04-25
              Brutalist architecture validation (building → city;
              building → different-building)
```

## sticky-rejection-blocks-manual-add

```
symptom:    after auto_score_by_description rejected a title,
              attempting to add it back manually returns "blocked
              by rejection" silently or with non-obvious feedback
detection:  add_articles call shows added=0; list_rejections shows
              the title with a rejection reason; the AI may not
              realize the rejection list is the cause
rescue:     unreject_articles(titles=[...]) before the manual
              add; future: gather tools should warn-and-allow on
              previously-rejected titles rather than silently skip.
evidence:   2026-04-24 AA-STEM cycle
```

---

# Metacognitive / process failures

The AI's overall posture failed in ways the catalog needs to name
explicitly because the AI won't notice them otherwise.

## shape-typed-first-move-skipped

```
symptom:    despite the SHAPE → WIKIDATA PROPERTY table or move
              catalog naming a high-leverage first move for the
              topic's shape, the AI defaults to "category sweep
              first" and never reaches for the recommended move
              (navbox, Wikidata property probe, cross-wiki, etc.)
detection:  retrospective: usage log shows zero calls to the
              shape-typed first move tool family on a topic shape
              that recommends one (zero harvest_navbox on Apollo 11;
              zero wikidata_query on orchids despite P171
              recommendation)
rescue:     active scaffolding at set_topic_rubric (Ship 2.a) —
              when the AI commits to a topic profile, the response
              returns the applicable moves so they arrive
              in-context at the moment of decision.
            Until Ship 2 lands: explicitly name the shape-typed
              first move in the rubric prose itself ("plan: navbox
              of parent program first").
evidence:   2026-04-24 thin-variant cycle (5 of 5 topics)
```

## calibration-pegged-at-protocol-following

```
symptom:    self-rating and confidence cluster tight (rating 7/10,
              confidence ~0.7) regardless of actual recall, which
              spans wide
detection:  retrospective comparison of submit_feedback rating /
              confidence vs gold-derived recall; the AI is using
              the rating as "I followed the protocol" rather than
              as a quality measurement
rescue:     decomposed calibration (Ship 3) — replace the single
              float with a structured signal vector (triangulation
              %, shape-strategies-attempted ratio, spot-check hit
              rate, redirect-collapse-rate, failure-modes-observed,
              yield-trajectory) and a server-derived band.
            Until Ship 3: at wrap-up, force the AI to cite at least
              two computable signals from describe_topic in the
              confidence rationale.
evidence:   2026-04-24 thin-variant cycle (rating 7 / conf ~0.7
              across recall 33%–85%)
```

## rubric-too-narrow-for-bounded-event

```
symptom:    rubric for a named-historical-event topic puts direct-
              flanking events and operationally-used facilities in
              OUT, when concentric-reach scoping treats them as
              PERIPHERAL. Result: silent recall loss on the
              program-tail axis even though precision looks clean.
detection:  rubric scope_text says "Other <adjacent events> are OUT"
              or "generic <parent-org / facility> articles are OUT"
              without distinguishing direct-flanking from non-
              flanking; mid-run spot check finds direct
              predecessors / successors / used-facilities absent
              from the corpus.
rescue:     redraft using the three-ring pattern in move:
              concentric-rubric-for-named-event. Direct-flanking
              and operationally-used belong in PERIPHERAL, not OUT.
            If the rubric already shipped and the run already
              over-pruned: unreject_articles on the flanking +
              used-facilities set before final cleanup.
evidence:   2026-04-26 apollo-11 thin run wrote "Other Apollo
              missions (1, 7-10, 12-17): OUT" — gold has Apollo
              8/10/12 (direct flanking) as IN. Same rubric put
              Kennedy Space Center, Mission Control Center, and
              Manned Space Flight Network as OUT — gold has them
              as PERIPHERAL. Phase-2 reach-extension recovered some
              but not all.
```

## cross-wiki-feature-confabulation

```
symptom:    on a non-en topic, the AI claims a Wikipedia feature
              (WikiProjects, list pages, specific templates) "does
              not exist" on the target wiki and skips the
              reconnaissance step, when in fact it does exist under
              a localized name. The result is a thin corpus and a
              false-confident user-facing statement.
detection:  AI emits an authoritative claim ("No WikiProject system
              exists on French Wikipedia") without a probe call
              having been made — check the tool-call log for a
              find_wikiprojects / search_articles call against the
              target wiki. Absence of probe + presence of confident
              claim = confabulation.
rescue:     run the probe with the wiki= parameter set; consult the
              wiki's conventions if the tool returns 0 (find a local
              equivalent via Wikidata sitelink, or search_articles
              with intitle:<local-namespace-prefix>); only conclude
              "absent" after empirical check.
evidence:   2026-05-13 WIPO/OMPI session — fr build received "No
              WikiProject system exists on French Wikipedia — as
              expected, this is an English-Wikipedia convention"
              from the AI without any find_wikiprojects(wiki='fr')
              call. fr-wiki has an active Projet: namespace with
              ~500+ projects linked via Wikidata to enwiki
              equivalents. Server-instruction text was the
              upstream cause (claimed "WikiProjects are essentially
              absent on non-en wikis"); fixed alongside cross-wiki
              tool extensions on 2026-05-13.
```

---

## Pointers

- Strategy moves catalog: `mcp_server/strategy_moves.md`
- Shape axes vocabulary: `mcp_server/shape_axes.md`
- Tool-API quirks: see `server_instructions.md` KNOWN SHARP EDGES
  (these are tool-wrapper behaviors, complementary to strategy
  failure modes)
- Ship 2's `audit_progress` diagnostic will scan corpus state for
  the detection cues here automatically and surface matched
  failure-modes-in-progress.

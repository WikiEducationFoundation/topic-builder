# Scope: orchids

Frozen: 2026-04-23. Revisit deliberately — a scope change invalidates
the gold audit.

## Short statement

Wikipedia articles about members of the Orchidaceae family (orchids)
and their immediate biology, taxonomy, cultivation, pollination,
phytochemistry, and cultural role. Includes orchid-focused people and
institutions; includes orchid cultural works; excludes non-Orchidaceae
plants and general botany unless orchid-specific.

## In scope

- **Orchid taxonomy.** Species, genera, subtribes, hybrids (natural
  and cultivated), cultivars, and named individual plants of the
  Orchidaceae family. Notable example genera: Phalaenopsis, Cattleya,
  Dendrobium, Vanda, Cymbidium, Oncidium, Vanilla, Bulbophyllum,
  Paphiopedilum, Epidendrum, Masdevallia, Laelia, Caladenia,
  Acianthera, Pleurothallis, Stelis, Lepanthes, Ornithocephalus.
- **Orchid-specific people.** Orchidologists, orchid hunters, orchid
  growers, orchid hybridizers, orchid breeders, orchid collectors,
  orchid nursery operators. Scientists whose primary published work
  is orchid taxonomy or orchid biology.
- **Orchid-specific institutions.** Botanical gardens that
  specialize in orchids, orchid societies, orchid research centers.
- **Orchid cultural works.** Books, documentaries, films whose
  primary subject is orchids (e.g. *The Orchid Thief* — but not
  necessarily its film adaptation unless that article is primarily
  about the orchid subject matter).
- **Orchid phytochemistry.** Chemical compounds identified in or
  isolated from orchids, including fragrance components and
  medicinal compounds.
- **Orchid pollination biology.** Articles about pollination
  mechanisms specific to orchids, orchid-symbiont mycorrhizae,
  orchid-pollinator coevolution.
- **Orchid pests, diseases, and conservation.** Pests and pathogens
  where the article's subject is the interaction with orchids;
  conservation status articles for orchid species.

## Explicitly out of scope

- **Non-Orchidaceae plants.** Roses, lilies, irises, any flowering
  plant family other than Orchidaceae. Even if the plant shares an
  orchid-species epithet, OUT.
- **General botany.** Pollination biology in general, plant taxonomy
  in general, flowering-plant evolution in general — OUT unless
  article is orchid-focused.
- **Name collisions.** Articles unrelated to orchids that happened
  to be pulled in by fuzzy search or list-page inclusion (e.g.
  semiconductor companies, actors, politicians whose names match
  orchid-species epithets or list entries).
- **Non-orchid figures from cross-wiki reconciliation.** Chinese
  artists/poets (Qu Yuan, Ma Shouzhen, Guan Daosheng) who are
  tangentially connected to orchid cultural tradition (e.g. via
  the Four Gentlemen motif) but whose primary notability is
  unrelated — default OUT; can be elevated to PERIPHERAL if a
  future audit expands cultural-tail coverage.

## Ambiguity rulings (default decisions)

- **General botanists.** PERIPHERAL default. A botanist who
  described orchid taxa but is also known for other families is
  peripheral to the orchids topic (e.g. Carl Ludwig Blume, Alfred
  Cogniaux, Achille Richard). The classifier uses this as the
  catch-all for "botanist" / "naturalist" / "biologist" /
  "horticulturist" / "explorer" descriptions.
- **Orchid phytochemicals.** IN. Chemical compounds from orchids
  whose articles are in category:Orchids count.
- **Four Gentlemen art tradition** ("Four plants in East Asian
  art"). The overarching cultural article is IN (orchid is one of
  the Four). Specific artists who painted the Four Gentlemen are
  OUT by default unless the article emphasizes their orchid-
  specific work.
- **Empty Wikidata shortdesc + orchid source.** IN (trust the source
  — the build context guarantees orchid relevance).
- **Cross-wiki-reconciliation manual sources.** Mostly IN (these
  are articles walked back to enwiki from other-language orchid
  builds). Non-botanical biographies from cross-wiki are OUT.

## Cross-wiki relevance

This benchmark's enwiki corpus is 18,122 articles. Parallel builds
exist on zhwiki (1,808), jawiki (367), ptwiki (2,265), nlwiki (135).
The cross-wiki walk was the biggest completeness-leverage strategy in
the original orchids build — 21 gap-fills were identified on the first
pass, but many more are likely reachable. A fresh run with the shipped
Chunks 1–6 + cross_wiki_diff (when it lands) would be the highest-
leverage ratchet move for this benchmark.

## Known scope revisits / open questions

- **Cultural-tail breadth.** Should we include the specific artists
  (Qu Yuan, Ma Shouzhen) who contributed to Four-Gentlemen orchid
  painting tradition? Currently OUT as peripheral to the topic's
  primary subject. Could elevate to PERIPHERAL on a future audit.
- **Orchid-in-literature individual works.** Currently we trust
  manual source inclusion. If a specific orchid-themed novel /
  film / poem gets cited but isn't captured, audit individually.
- **Taxonomic scope of "orchid".** We default to the APG-current
  consensus on Orchidaceae. Some articles about closely-related but
  non-Orchidaceae plants (e.g. some Apostasioideae species, which
  ARE Orchidaceae despite divergent morphology) are IN if their
  article classifies them as Orchidaceae.

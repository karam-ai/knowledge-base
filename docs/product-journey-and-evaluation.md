# Product draft — GulfSignal (working name)

**Status:** proposal, not a launched product. **Starting point:** the standalone Podcast Knowledge Graph API, not the private Obsidian vault.

## Positioning and first customer

**GulfSignal** helps European industrial-software vendors and boutique GCC consultancies understand what people in Saudi Arabia, the UAE and Qatar are *actually saying* about industrial AI, predictive maintenance and energy operations. It transforms licensed/public interviews, podcasts and conference panels into a reviewable evidence timeline and decision brief. It is not another generic podcast chatbot, media player, or proof that an interviewee's statement is true.

The prior internal research (`ollama-device-agent/product/market-and-competitor-research.md` and `business-model-suggestion.md`, October 2026) identified cross-episode chat and timestamp citations as baseline. Current competitor pages for PodPast and Podscan independently confirm overlapping timestamped answers and monitoring offerings [1][2]. Our proposed differentiation is **Arabic–English industrial-domain intelligence with cross-source disagreement, dated claim/prediction tracking, official-source verification and reusable market-entry dossiers**. This remains a hypothesis until customers validate it.

**Initial wedge:** one question for one buyer: *"How are Saudi and UAE industrial operators discussing AI for predictive maintenance, and where do their stated constraints differ?"* Start with a curated set of 50–100 sources whose processing rights are recorded. The existing 1,198 imported episodes and 22,075 passages are useful for engineering tests but are not a curated GCC industrial corpus. Do not republish that private collection to test users.

## Current working slice versus future product

| Capability | Current state | Required for credible pilot |
|---|---|---|
| Ingest | JSON passages and SRT episode transcript | Scheduled rights-aware publisher ingestion; reviewed speaker/date metadata |
| Retrieval | SQLite lexical FTS5 | Arabic/English semantic + lexical retrieval, topic/date/country filters, reranking |
| AI answer | Local Ollama adapter; returns validated verbatim quote + passage ID + start/end | Citation-to-audio links, better model, confidence/abstention evaluation |
| Graph | RDF passages and conservative vocabulary | Reviewed entities, organizations, projects, claims, temporal relations |
| Publication | Single local FastAPI instance and static UI | Authenticated multi-user pilot, tenant isolation, backups, content-rights gates |
| Verification | No external verification in answer endpoint | Separate, cited official-source fact-check workflow |

### What `/v1/answer` does now

1. Lexically retrieve a small number of candidate passages from app-owned SQLite.
2. Send only selected excerpts to a **local Ollama** chat model via `/api/chat` with a JSON schema [3]. No external LLM provider is configured by default.
3. Require structured findings with a retrieved passage ID and a quote that is literally present in that passage.
4. Attach server-owned episode title, source ID, language and start/end timestamps to each accepted finding. Invalid citations/quotes are dropped; zero valid findings means *insufficient evidence*.
5. State that podcast-derived claims are not independently verified facts.

**Limitations:** Lexical English queries do not reliably find Arabic evidence; speaker metadata and publication dates are not present for most imported records; short quotations are checked for textual match but the model's paraphrase is not semantically proven; audio links are often unavailable. Running a local model over a busy CPU can be slow or time out. This is an experimental evidence-linked answer, not a reliable decision engine.

## Researcher user journey

1. **Choose a dossier**: country, industrial subtopic, period, companies, language, and whether private sources are permitted. Show corpus coverage and source rights.
2. **Search evidence**: inspect original-language excerpts with title, source date, speaker (if verified), timestamp and playback link (if available). No LLM required.
3. **Ask a question**: see a synthesized answer as separately attributed findings; click each citation to inspect the exact passage and original media. The interface displays *no evidence* when retrieval or quote checks fail.
4. **Compare**: see agreement, disagreement, assumptions and unresolved claims across speakers and time; filter out low-quality transcripts.
5. **Verify**: compare interview claims against official data/primary sources in a distinct panel. Never quietly upgrade an interviewee's statement to a verified fact.
6. **Decide**: save an analyst-edited brief containing a takeaway, confidence, counterevidence, decisions/open questions and an evidence appendix; export only as allowed by source rights.
7. **Monitor**: subscribe to a company/topic; new approved sources update the dossier, and the user sees what changed and why.
8. **Give feedback**: mark useful/irrelevant passage, wrong timestamp, speaker error, unsupported claim or missing opposing view; send to a review queue, not directly into training.

**Administrator journey:** connect or upload allowed sources → record license/use policy and provenance → transcribe/align timestamps → verify speaker/date/language and Arabic names → index → run retrieval/citation checks → approve publication → monitor removals and opt-outs. Private workspace data stays separate from public sources.

## Training and evaluation procedure (draft)

**Do not start by fine-tuning on scraped third-party transcripts.** The first "training" loop is retrieval and citation evaluation; only later consider rights-cleared model adaptation.

1. **Define the task and rights**: identify permitted audio/transcripts, intended storage, model provider, retention and display limits. Exclude private vault material from public demo/training and external evaluation uploads unless explicitly authorized.
2. **Create a gold set**: ~50 analyst-authored questions for the wedge, covering Arabic, English, transliterations, named entities, conflicting claims, absent answers and ambiguous timestamps. Have two reviewers mark relevant episode IDs, exact passage IDs, quote spans, speaker/date where known and acceptable abstentions. Split by episode/source before tuning so near-duplicate chunks do not leak.
3. **Baseline retrieval**: benchmark current FTS5 on exact passage recall@k and episode recall@k separately; log query language, source coverage and latency. Compare against an Arabic–English embedding index and hybrid fusion only after the baseline. Do not assume semantic search helps without measurement.
4. **Prompt and model evaluation**: version the retrieval settings, prompt, model identifier, output schema and temperature. Run the gold set offline with local models. Measure quote-substring validity, passage-ID validity, answer support by human review, disagreement preservation, abstention on unanswerable questions and p50/p95 latency. Model output is untrusted data; keep citation construction server-side.
5. **Error review**: tag retrieval miss, chunk boundary error, ASR error, translation error, wrong entity/speaker, unsupported paraphrase, invented date, or answer-model failure. Fix the dominant error class first; rerun unchanged holdout questions after every change.
6. **Human-reviewed enrichment**: for an approved source, extract candidate organization/person/project aliases and claim types. Reviewer confirms Arabic spelling, romanization, role, date, contradiction and evidence span before promoting it to the graph.
7. **Only then consider fine-tuning**: if recurring domain terminology is a measured failure and rights allow, create a separate de-identified, licensed dataset; hold out complete sources and time windows; compare a tuned model against retrieval/prompt improvements. Never train on user-private interviews by default.
8. **Continuous quality gate**: block rollout when quote validity or citation mapping regresses; keep an audit trail of question, retrieved IDs, selected passages, model/prompt version, accepted findings and user correction, with privacy-aware retention.

**Candidate pilot gates (targets to negotiate, not current results):** >90% exact-passage recall@10 on reviewed wedge questions, 100% accepted quotes present verbatim in the cited passage, >90% analyst-rated supported answer findings, no public-private source leaks, and a measurable reduction in analyst briefing time. Validate these with design partners; do not claim them today.

## Delivery and revenue experiment

- **Discovery:** interview 10 accessible European industrial-vendor strategy/market-entry researchers and GCC boutique consultancies; ask what decisions rely on interviews, how long review takes, what evidence their buyers need, and what transcripts they can lawfully use.
- **Concierge pilot:** one buyer, one topic, Saudi Arabia/UAE, 50–100 curated rights-cleared sources, weekly reviewed brief and searchable evidence workspace, six to eight weeks. Pricing in earlier research (€3k–€7.5k small pilot; €7.5k–€20k professional pilot) is *an unvalidated pricing hypothesis*, not market data.
- **Success criterion:** buyer repeatedly uses and pays for a specific output (e.g. sourced market-entry brief), can audit citations, and reports time saved over their existing workflow. If not, change the wedge before scaling ingestion or infrastructure.
- **Enterprise step:** identity, isolation, deletion, audit logging, backups, jurisdiction and licensing agreements come before onboarding confidential material. Current unauthenticated read/search/export endpoints are not appropriate for external users or private data.

## Near-term build order

1. Demonstrate `/v1/answer` on a small synthetic/rights-cleared corpus and review citation validity.
2. Fix retrieval quality and capture episode publication date, speakers, original URLs and rights.
3. Add a curated GCC industrial collection, Arabic/English hybrid search and analyst review.
4. Add claim comparison/timeline and official-source verification as separate layers.
5. Add access control and source-level display policies before any test-user deployment.
6. Run discovery calls and the paid design-partner pilot before considering model fine-tuning or a generalized API business.

## Sources

[1] PodPast product page — https://podpast.ai/ (current product positioning, checked during drafting).
[2] Podscan brand monitoring — https://podscan.fm/for-brands (current brand monitoring features, checked during drafting).
[3] Ollama chat API documentation — https://docs.ollama.com/api/chat (JSON-schema `format` on `/api/chat`, checked during drafting).

Internal basis: `ollama-device-agent/product/business-model-suggestion.md` and `market-and-competitor-research.md` (October 28, 2026); `Knowledge Base/Podcasts/Podcast KB POC Architecture.md`. These are hypotheses and architecture notes, not independent evidence of buyer demand.

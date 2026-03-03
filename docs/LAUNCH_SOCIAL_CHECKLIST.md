# TelsonBase — Social Media Launch Checklist
**Drop date:** March 6, 2026
**Sequence matters.** GitHub first. Everything else links back to it.

---

## Phase 1 — Own Properties First (Before You Post Anywhere)

These go live on drop day, before any community posts. You need something to link to.

- [ ] **GitHub repo live** — public, README with screenshots + GIFs, marked pre-release/beta
- [ ] **HuggingFace Space live** — `huggingface.co/spaces/QuietFireAI/TelsonBase` — see setup steps below
- [ ] **Update website GitHub links** — replace `href="#"` in nav/footer with actual repo URL
- [ ] **YouTube channel** — create if not already set up. Channel name: `TelsonBase` or `Quietfire AI`. Upload the 3 MP4 voice-over videos. Titles below.
- [ ] **Medium publication** — publish launch post. Draft below.
- [ ] **audiooverviews.io** — publish first audio overview (NotebookLM on the README or technical defense brief is a natural first piece). Cross-link to GitHub.
- [ ] **videooverviews.io** — embed or link the YouTube MP4s. Announce the platform opening with TelsonBase as the launch subject.

---

## HuggingFace Space — Setup Steps (Do Before Drop Day)

HuggingFace indexes in the HF search and discovery feed. Your audience there: ML practitioners, AI researchers, and practitioners building agent pipelines — exactly the right people.

**One-time setup:**
1. Go to huggingface.co → sign in (or create account)
2. Create organization: `QuietFireAI` (Settings → Organizations → New org)
3. Under QuietFireAI org → New Space
   - Space name: `TelsonBase`
   - SDK: **Static**
   - License: Apache 2.0
   - Visibility: Public
4. Clone the new Space repo locally:
   ```bash
   git clone https://huggingface.co/spaces/QuietFireAI/TelsonBase
   ```
5. Copy in the two files from the main repo's `huggingface_space/` folder:
   - `README.md` (Space card + YAML frontmatter)
   - `index.html` (landing page)
6. Commit and push:
   ```bash
   git add README.md index.html
   git commit -m "Initial Space: TelsonBase zero-trust AI agent governance"
   git push
   ```
7. Space goes live at: `https://huggingface.co/spaces/QuietFireAI/TelsonBase`

**After GitHub goes public:** The Space links directly to the GitHub repo — no further changes needed.

**HuggingFace post in community feed:**
- After Space is live, post a short announcement in the HF community tab of the Space
- Tag: `ai-governance`, `zero-trust`, `self-hosted`, `mcp`

---

## Phase 2 — Hacker News (Highest ROI, Do This First Among Communities)

Show HN is the single best developer distribution channel for a tool like this. A good thread here drives GitHub stars, Reddit cross-posts, and newsletter pickups.

- [ ] **Create HN account** (news.ycombinator.com) if you don't have one — needs age to rank, post on drop day morning (8–10am ET performs best)
- [ ] **Post title:** `Show HN: TelsonBase – self-hosted zero-trust governance for AI agents`
- [ ] **Comment with:** one paragraph on what problem it solves, link to GitHub, link to the kill-switch GIF or MP4. Be in the thread for 2–3 hours answering questions.
- [ ] **Lobste.rs** (lobste.rs) — smaller than HN, invite-only, strong signal/noise. If you can get an invite, post same day. Tag: `ai`, `security`, `self-hosted`

---

## Phase 3 — Reddit (Priority Order)

Each post needs a different angle — don't cross-post the same text.

| Subreddit | Angle | Post title |
|---|---|---|
| r/selfhosted | Self-sovereignty + no vendor lock-in | "I built a self-hosted governance layer for AI agents — kill switch, HITL approval, audit chain, 12 Docker services" |
| r/LocalLLaMA | Local AI + control | "TelsonBase: zero-trust governance for local AI agents. Trust tiers, kill switch, human approval gate." |
| r/MachineLearning | Safety + agent behavior | "Self-hosted AI agent governance platform — earned trust tiers, behavioral scoring, HITL. Open source." |
| r/netsec | Security posture | "Built an AI agent governance layer with tamper-evident audit chain, kill switch, and CAPTCHA-gated registration." |
| r/docker | Tech stack | "12-service Docker stack for AI agent governance — Redis, Postgres, Traefik, Celery, Mosquitto, Grafana, Prometheus" |
| r/Python | FastAPI + architecture | "Open-sourced TelsonBase — FastAPI AI governance platform. 720 tests, Bandit clean, full MCP integration." |
| r/devops | Ops angle | "AI agents running in production need a governance layer. Here's what I built." |
| r/artificial | Broad AI audience | "Self-hosted platform that governs AI agents — trust tiers, behavioral scoring, human-in-the-loop approval" |
| r/AIAssistants | End-user angle | "TelsonBase: put a kill switch and approval queue in front of your AI agents" |
| r/cybersecurity | Enterprise angle | "SOC2-ready AI agent governance — audit chain, RBAC, HITL, zero external dependencies" |

**Reddit rules:**
- Post in one subreddit at a time, 1–2 hours apart
- r/selfhosted and r/LocalLLaMA are the highest expected return — do those first
- Read the sidebar before posting — some subs ban self-promotion or require flair
- Respond to every comment in the first 2 hours

**Facebook groups to check:**
- "Self-Hosted" groups (there are several large ones, search for it)
- "AI/ML Practitioners" or similar developer AI communities
- "Docker and Containers" groups
- Local tech entrepreneur / founder groups in your area
- These are lower yield than Reddit for developer tools but worth the 20 minutes

---

## Phase 4 — Medium

You have the account and the publication. Publish the launch post there.

**Title options:**
- "Why Every AI Agent Deployment Needs a Kill Switch"
- "I Built a Zero-Trust Governance Layer for AI Agents — Here's Why"
- "The Problem With AI Agents Running Unsupervised in Production"

**Structure:**
1. The problem (agents acting autonomously with no governance)
2. What TelsonBase does (3 capabilities: trust tiers, kill switch, HITL)
3. Embed the 3 GIFs or YouTube videos inline
4. Link to GitHub

**Cross-post to Dev.to** (dev.to) — same article, same content. Dev.to has strong organic SEO and a large developer audience. Use the canonical URL pointing to Medium.

---

## Phase 5 — LinkedIn

- [ ] Personal post (not company page — personal posts get 3–5x the reach)
- [ ] Angle: builder perspective — "I spent 3 months building this. Here's what AI agent governance actually requires."
- [ ] Attach the kill-switch MP4 directly to the LinkedIn post — video native to LinkedIn performs best
- [ ] Tag: `#AIGovernance` `#OpenSource` `#AIAgents` `#SelfHosted`

---

## Phase 6 — Twitter/X and Discord

**Twitter/X:**
- [ ] Thread format performs better than single posts for technical tools
- [ ] Thread: 1) What it is 2) Kill switch demo (embed GIF) 3) HITL approval demo (embed GIF) 4) Link to GitHub
- [ ] Tag: `#OpenSource` `#AIGovernance` `#SelfHosted` `#LLM` `#AIAgents`

**Discord communities worth joining:**
- LocalAI Discord (if there is one — active self-hosted AI community)
- LangChain / LlamaIndex Discord — these communities use agents heavily and need governance tooling
- Goose (by Block) Discord — TelsonBase has native Goose/MCP integration, this is a direct fit
- AI safety / AI governance servers

---

## Phase 7 — Press and Newsletters (Longer Lead Time)

These won't move on drop day — plant seeds 1–2 weeks before or pitch day-of and wait.

**Most likely to cover an open-source self-hosted AI tool:**
- **The Register** — covers enterprise tech and security. Angle: AI agent kill switch, SOC2-ready governance.
- **Ars Technica** — covers open-source and developer tools. Angle: self-hosting movement + AI agent safety.
- **VentureBeat** (AI coverage) — they cover AI infrastructure and governance. Email their AI beat reporter.
- **InfoQ** — developer-focused, covers architecture and platform engineering. Will pick it up if HN thread does well.
- **DZone** — developer community with original articles. Submit directly at dzone.com/write-for-us.

**Newsletters that cover this space:**
- **Import AI** (Jack Clark) — AI infrastructure and safety. Submit tip via newsletter form.
- **The Batch** (deeplearning.ai) — covers AI research and tooling.
- **Last Week in AI** (lastweekin.ai) — curated weekly roundup. Submit via their form.
- **TLDR Tech** (tldr.tech) — 1.5M+ subscribers. Submit links at tldr.tech/tech/submit.

**Angle for press pitches:**
> "AI agents are running in production with no kill switch. TelsonBase is a self-hosted governance platform — earned trust tiers, kill switch, human-in-the-loop approval, tamper-evident audit chain. Open source, zero external dependencies, Apache 2.0."

---

## YouTube Video Titles (for the 3 MP4s)

| GIF | YouTube title |
|---|---|
| governance-blocked | TelsonBase: AI Agent Action Blocked in Real Time (Under 100ms) |
| kill-switch | TelsonBase: Kill Switch — Suspend an AI Agent Instantly |
| hitl-approval | TelsonBase: Human-in-the-Loop — AI Agent Action Held for Approval |

Add these to a playlist: `TelsonBase Demos`
Description on all three: Link to GitHub, link to telsonbase.online, one-sentence summary.

---

## Sequencing Summary

| Day | Action |
|---|---|
| Drop day morning | GitHub goes public → update website links |
| Drop day morning | HuggingFace Space goes public (flip visibility if pre-staged, or push files) |
| Drop day 8am ET | Hacker News Show HN post |
| Drop day 9am | r/selfhosted post |
| Drop day 10am | r/LocalLLaMA post |
| Drop day 11am | YouTube videos live |
| Drop day noon | Medium article publishes |
| Drop day 1pm | LinkedIn post (attach kill-switch MP4) |
| Drop day 2pm | Twitter/X thread |
| Drop day afternoon | r/netsec, r/MachineLearning, r/docker |
| Drop day eve | r/Python, r/devops, r/artificial |
| Day 2 | Dev.to cross-post, audiooverviews.io, videooverviews.io |
| Day 3+ | Discord communities, newsletter submissions, press pitches |
| Week 2 | Follow up on press pitches, reply to any late Reddit threads |

---

## Accounts to Create Before Drop Day

- [ ] HuggingFace — create account + QuietFireAI org + TelsonBase Space (see HuggingFace setup above)
- [ ] Hacker News (if not already)
- [ ] YouTube channel (TelsonBase or Quietfire AI)
- [ ] Twitter/X (if not already active)
- [ ] Dev.to account (dev.to)
- [ ] Lobste.rs (get invite — post in r/lobsters or ask in HN thread)
- [ ] LinkedIn company page (optional — personal post is higher yield)

---

---

## Phase 8 — ORCID and Academic Citation (Do This Before Drop Day)

**Yes, register.** ORCID is open to anyone — no degree, no institution required. The point of it is persistent scholarly identity, and independent practitioners building verifiable open-source tools are exactly who it's designed for. AI governance is new enough that a working, tested, deployed platform carries more weight than most credentialed papers. Register now and be listed before anything gets published.

**Steps:**
- [ ] Register at orcid.org — free, takes 2 minutes. Get your 16-digit ORCID iD (format: 0000-0000-0000-0000)
- [ ] Add TelsonBase as a "Software" work on your ORCID profile (Works → Add → Software)
- [ ] Add any Medium articles you publish as "Journal article" or "Preprint" works on ORCID
- [ ] Put your ORCID iD badge in the README author section and on your Medium profile
- [ ] Add `CITATION.cff` to the GitHub repo root (see below) — GitHub auto-generates a "Cite this repository" button from it

**CITATION.cff** — add this file to the repo root before the drop:
```yaml
cff-version: 1.2.0
message: "If you use TelsonBase in your research, please cite it using this metadata."
title: "TelsonBase"
version: 9.0.0B
date-released: 2026-03-06
authors:
  - name: "Quietfire AI"
    orcid: "https://orcid.org/YOUR-ORCID-ID"
license: Apache-2.0
repository-code: "https://github.com/YOUR-USERNAME/telsonbase"
abstract: "Self-hosted zero-trust AI agent governance platform. Earned trust tiers, kill switch, human-in-the-loop approval, tamper-evident audit chain."
keywords:
  - ai-governance
  - ai-agents
  - zero-trust
  - self-hosted
  - human-in-the-loop
```

**Zenodo** (zenodo.org) — free CERN-hosted archive. Connects directly to GitHub:
- [ ] Create Zenodo account, link GitHub
- [ ] On GitHub: create a release tagged v9.0.0B on drop day
- [ ] Zenodo auto-archives it and issues a DOI (e.g. `10.5281/zenodo.XXXXXXX`)
- [ ] Add that DOI badge to the README
- [ ] Now TelsonBase is permanently citable in academic literature, forever, regardless of what happens to GitHub

Once you have a DOI, researchers can cite TelsonBase in papers. That's how independent practitioners build a citation trail without institutional affiliation — the work cites itself.

---

## Phase 9 — International Communities and Organizations

**EU AI Act is your angle for Europe.** The Act is now in force. TelsonBase's audit trail, human oversight gate, and trust tiers map directly to the high-risk AI system requirements in the Act. European companies need tooling. That's not marketing spin — it's a real compliance story.

**International tech press worth pitching:**
- **Heise Online** (heise.de) — largest German tech publication, significant EU readership. AI governance + EU AI Act compliance angle lands here.
- **The Register** (already on list) — UK-based, global developer readership
- **ZDNet** — US-origin but international editorial, covers enterprise AI infrastructure
- **Le Monde Tech / Numerama** (France) — French tech press, EU AI Act is a major topic

**International research and standards organizations:**
- **OWASP AI Security Project** — OWASP maintains the LLM Top 10 security risks. TelsonBase directly addresses several of them (LLM08: Excessive Agency, LLM09: Overreliance). Submit a tool listing or open a discussion on their GitHub. Global security community, highly credible.
- **NIST AI RMF community** — NIST's AI Risk Management Framework has a public stakeholder community. TelsonBase's governance model aligns with their "Govern" and "Manage" functions. Engage via nist.gov/artificial-intelligence.
- **IEEE Technical Committee on Autonomous Systems** — if you write a short technical paper, this is the academic venue. Not urgent, but the long-term credibility play.
- **ENISA** (EU Agency for Cybersecurity) — they publish AI security guidelines and maintain a community. Submitting TelsonBase as a reference implementation for AI agent governance is plausible.
- **AI Safety Institute** (UK DSIT) — UK government body on AI safety. They track tooling and infrastructure. Worth a cold email with the GitHub link.

**International developer communities:**
- **Dev.to** already covers this — international audience
- **Hashnode** — developer blogging platform, strong international community (India, EU, LatAm). Cross-post the Medium article there too.
- **lobste.rs** — invite-only but international, technically sophisticated
- **SSRN** (ssrn.com) — preprint server for law, policy, and tech. A short paper on AI agent governance architecture would be appropriate here and gets indexed by Google Scholar.

**Reddit international angle:**
- r/GDPR and r/privacy — EU AI Act + GDPR intersection, governance tooling for compliance
- r/AIGovernance (if active) — niche but targeted

**The short version for EU outreach:**
> "TelsonBase is a self-hosted AI agent governance platform. Audit trail, human oversight gate, and trust tiers align with EU AI Act requirements for high-risk AI systems. Apache 2.0, zero external dependencies, deployable in your own infrastructure."

That sentence gets attention from EU compliance teams in a way that the general developer pitch doesn't.

---

*TelsonBase v9.0.0B · Quietfire AI · March 2, 2026*

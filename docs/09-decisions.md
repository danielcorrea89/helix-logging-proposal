[← Home](../README.md) &nbsp;|&nbsp; [← Risks](08-risks.md) &nbsp;|&nbsp; Next: [Appendix →](appendix.md)

# 9 — Decision Rationale & Alternatives 🧭

> [!NOTE]
> This document explains *why* each major technology was chosen, what alternatives were rejected, and what the choice costs us. Architectural trade-offs (federated vs centralised collection, isolated vs shared workspaces) live in [Options](02-options.md) and [Cost Model](06-cost-model.md). This doc covers **tooling** decisions on top of that architecture.

---

## 🧠 The Meta-Decision — Azure-Native vs Third-Party Stack

Before any individual tool was chosen, the platform stack itself was a decision: lean **Azure-native** (Sentinel, Log Analytics, AMA, Azure Policy, Lighthouse), or assemble a best-of-breed mix (e.g. Splunk Cloud SIEM, Datadog APM, ELK for storage, Fluent Bit for collection).

### What Azure-native buys

| Property | Why it matters here |
|---|---|
| **First-party Entra / Lighthouse / M365 integration** | The cross-tenant security model *is* Entra + Lighthouse + PIM. A third-party SIEM still has to authenticate into Azure to read the data — meaning every alternative reintroduces the same trust-boundary problem the architecture was designed to eliminate, and adds a second one (the SIEM's own identity surface). |
| **Single-vendor support model** | A small team supporting multi-tenant security infrastructure cannot afford a ticket to bounce between Microsoft and a third-party vendor when M365 audit ingestion breaks at 2am. |
| **Native data residency in client tenants** | Lighthouse keeps the *delegation* in Helix's tenant while the *data* stays in the client's. Most third-party SIEMs require the data to leave the client's tenant to be indexed — directly contradicting the federated model. |
| **No additional egress** | Azure Monitor → Sentinel is in-region, no public-internet hop. Pushing to a third-party SaaS adds egress costs and a public-internet TLS path on every event. |
| **Predictable commitment-tier pricing** | Sentinel + LAW pricing is published, in dollars per GB, with stacking commitment discounts. Several third-party tools price on indexed volume × retention × users × hosts × features — much harder to forecast for a multi-tenant platform with per-client billing. |

### What it costs us

| Cost | What we accept |
|---|---|
| **Vendor lock-in at the data-store layer** | Migrating off Log Analytics is non-trivial — KQL queries, analytics rules, and workbooks would need re-platforming. Mitigated by keeping the *application* instrumentation on OpenTelemetry (vendor-neutral) so the source of telemetry is portable even if the sink is not. |
| **Sentinel pricing premium at very high volume** | At 500GB/day+ per workspace, Splunk's tiered enterprise pricing or a self-hosted ELK cluster can be cheaper *per GB*. Counter-argument: at that volume, the operational cost of running ELK exceeds the per-GB delta — see [SIEM decision](#1--siem-microsoft-sentinel) below. |
| **Smaller community detection-rule ecosystem than Splunk** | Splunk has the larger SIEM community by a wide margin. Sentinel's rule library is good and growing, and analytics rules are MITRE ATT&CK-mapped, but the gap is real for niche detections. |
| **Some KQL learning curve for engineers used to SPL or Lucene** | Mitigated by KQL being a small language and the team already operating in Azure. |

### When we'd revisit

- A client contractually requires logs in a specific third-party SIEM (e.g. a SOC service that runs on Splunk) — handled by **adding** an export path, not replacing the platform.
- Aggregate platform volume reaches a tier where Splunk Cloud or a managed ELK becomes meaningfully cheaper *after* accounting for the ops cost of running it. That break-even point is in the high hundreds of GB/day per tenant — well beyond Helix's near-term scale.

---

## 1. 🛡️ SIEM — Microsoft Sentinel

### Decision summary

| | |
|---|---|
| **Choice** | Microsoft Sentinel on every client LAW + the shared LAW |
| **Alternatives considered** | Splunk Enterprise Cloud · Datadog Cloud SIEM · Sumo Logic Cloud SIEM · Self-hosted Elastic / OpenSearch + a SIEM layer (e.g. Wazuh, SIEMonster) |
| **Cost shape** | ~$2.46/GB ingested into a Sentinel-enabled workspace, on top of the underlying LAW Analytics ingestion (~$2.30/GB). Commitment tiers reduce both by 15–25% from ~100 GB/day. |
| **Operational shape** | Zero infrastructure to operate. Analytics rules, hunting queries, and playbooks deploy as code (ARM/Bicep/Pulumi). Native connectors for M365, Defender, Entra, and 100+ third-party sources. |

### Why not the alternatives

| Alternative | Why not (here) |
|---|---|
| **Splunk Enterprise Cloud** | Strongest detection-engineering ecosystem, but: (a) list pricing is materially higher than Sentinel at the volumes Helix expects (Splunk SVC/ingest pricing vs. ~$4.76/GB combined Sentinel+LAW); (b) no first-party M365/Entra connector — requires a Splunk add-on that re-authenticates against Microsoft Graph, which would need its own service principal in every client tenant (the exact thing Lighthouse exists to avoid); (c) introduces a second vendor support relationship for the most security-critical part of the platform. |
| **Datadog Cloud SIEM** | Excellent UX and APM/SIEM correlation, but: (a) all log data must leave the client tenant and land in Datadog's region — directly conflicts with the federated data-residency model; (b) indexing+retention pricing makes per-client cost attribution opaque; (c) Datadog's Azure connector pulls via diagnostic settings — same M365 connector gap as Splunk. |
| **Sumo Logic** | Continuous-tier pricing is competitive, but the same data-egress and connector-gap concerns apply as Datadog, plus a smaller Azure-aware feature set. |
| **Self-hosted Elastic / OpenSearch + Wazuh** | Lowest *per-GB* storage cost, highest *operational* cost. Cluster operations (upgrades, hot/warm tiering, snapshot management, security hardening) are a 1–2 FTE responsibility at multi-tenant scale. The brief explicitly calls out a small team — this option spends the team's capacity on platform plumbing instead of detection engineering. |

### Trade-offs accepted

- KQL is the only query language. Engineers familiar with SPL or ES|QL re-learn the syntax (small).
- Detection-rule community is smaller than Splunk's. Mitigated by Sentinel's curated rule galleries and MITRE coverage.
- Workspace-per-client + Sentinel-per-workspace means Sentinel-tier charges replicate per tenant. Mitigated by **rule-coverage tiering** (see [Automation §Detection Rule Lifecycle](07-automation.md#-detection-rule-lifecycle)) — standard clients receive a baseline rule set; high-sensitivity clients receive full coverage. The *enabling* of Sentinel is required for connectors and cross-workspace queries; the *cost* is dominated by analytics rule volume, not workspace count.

### When to revisit

If a client's SOC standardises on a different SIEM, attach an **export pipeline** (Event Hub → client SIEM) rather than replacing Sentinel. Sentinel remains the source of truth; the third-party tool becomes a downstream consumer.

---

## 2. 🗄️ Log Store — Azure Log Analytics

### Decision summary

| | |
|---|---|
| **Choice** | Azure Monitor Log Analytics with three tiers: Analytics ($2.30/GB) · Basic ($0.50/GB) · Archive ($0.02/GB-month) |
| **Alternatives considered** | Datadog Logs · Splunk Cloud · Self-hosted Elastic / OpenSearch · BigQuery / Snowflake (analytics-style) · Loki + S3 |
| **Cost shape** | Tiered at ingestion via DCR transformations. Verbose data routed to Basic before it lands; security data to Analytics; everything ages to Archive. Commitment tiers (100/200/500/1000/2000/5000 GB/day) discount Analytics by ~15–65%. |
| **Operational shape** | Fully managed, native to the SIEM, no cluster operations. |

### Why not the alternatives

| Alternative | Why not (here) |
|---|---|
| **Self-hosted Elastic / OpenSearch** | Per-GB cost can drop below $0.20/GB at scale, but you're trading *cloud cost* for *engineering cost*. Realistic operational cost for a multi-tenant security cluster (HA, snapshots, ILM, security hardening, version upgrades) is 1–2 FTE; that's $200K–$400K/year *before* infrastructure. The tier discount we'd save is much smaller than that until volumes reach hundreds of GB/day. |
| **BigQuery / Snowflake** | Excellent for analytics on cold/large data; weak for sub-minute security alerting. Would force a hybrid (hot store + cold store), doubling the surface area to operate. Reserved as a *future* option for archive analytics if Archive-tier query becomes a bottleneck. |
| **Datadog / Splunk Cloud Logs** | Same data-egress and per-tenant-attribution issues as the SIEM alternatives — see §1. |
| **Loki + S3** | Cheap, but unstructured, no SIEM integration, no native Entra/M365 connectors. Wrong tool for the security-log use case. |

### Why the three-tier model is the cost answer

The cost model assumes verbose simulation logs (container stdout, NVA flow logs) make up the majority of volume but only a minority of value. Routing them to Basic at ingestion via DCR transformations turns ~$2.30/GB ingested into ~$0.50/GB ingested — a **78% reduction on the cheapest 60–70% of total volume**. This single decision is worth more than any SIEM-vendor swap.

### Trade-offs accepted

- **Basic Logs cannot back Sentinel analytics rules.** Anything required for alerting or audit must be in Analytics — this is enforced in the per-source tier table (see [Cost Model §Per-Source Tier Assignment](06-cost-model.md#-per-source-tier-assignment)).
- **Archive query has restore latency** (~hours for ad-hoc, < 12 minutes for search jobs). Not appropriate for live incident triage; appropriate for compliance and forensics.
- **Workspace migration is hard.** Mitigated by keeping schema-friendly OTel instrumentation upstream — the *producers* are portable.

---

## 3. 🔦 Cross-Tenant Access — Azure Lighthouse

### Decision summary

| | |
|---|---|
| **Choice** | Azure Lighthouse delegation, scoped to the LAW resource group, granted to a PIM-eligible group in Helix's tenant |
| **Alternatives considered** | Guest users (Entra B2B) per Helix admin · A dedicated service principal per client tenant · Multi-tenant app registration with admin consent · Federation via cross-tenant access settings + RBAC |
| **Cost shape** | Lighthouse itself is **free**. Cost is in PIM (included with Entra ID P2) and the operational cost of administering delegations. |
| **Operational shape** | Onboarding deploys an ARM template into the client's subscription via Pulumi; thereafter, queries run as if the client workspace were native to Helix's tenant. |

### Why not the alternatives

| Alternative | Why not (here) |
|---|---|
| **Guest users (Entra B2B), one invitation per Helix admin per client tenant** | At N admins × M clients, you get N×M guest accounts — operationally untenable. Each guest exists *inside the client's directory*, so revocation requires action by the client (or a guest-cleanup automation that itself needs cross-tenant access). PIM coverage of guests is awkward. The audit trail splits across two tenants in a way Lighthouse's does not. |
| **Service principal per client tenant** | Solves the user-explosion problem but creates a *credential*-explosion problem: N SPs each with a secret/cert that must be rotated, stored, and protected. A leaked SP is permanent standing access to one client's data — exactly what PIM is designed to prevent. |
| **Multi-tenant app registration + admin consent** | Closer to right shape (one app, N consents), but each consent grants *application* permissions that aren't easily JIT-elevated through PIM. You'd end up rebuilding PIM on top of it, badly. |
| **Cross-tenant access settings (Entra cross-tenant sync / external collab.)** | Manages identity federation, not resource access — orthogonal capability. |

### Trade-offs accepted

- **Lighthouse is Azure-only.** Doesn't help if a client lives in AWS or GCP. Out of scope for Helix's brief, but worth flagging if multi-cloud client tenants ever become a requirement.
- **The delegation list itself is sensitive metadata** — knowing which clients exist is a valuable target. Mitigated by access controls on the managing-tenant subscription.
- **Lighthouse depth is limited to specific resource providers**; not every Azure RBAC operation is delegatable. For *Log Analytics Reader* and *Resource Policy Contributor* the support is full.

---

## 4. 🐍 Infrastructure as Code — Pulumi (Python)

### Decision summary

| | |
|---|---|
| **Choice** | Pulumi with Python, using `ComponentResource` to model the per-client logging baseline as a reusable class |
| **Alternatives considered** | Terraform (HCL) · OpenTofu · Bicep · ARM templates · Crossplane · CDK for Terraform (CDKTF) |
| **Cost shape** | Pulumi OSS is free; Pulumi Cloud (state + RBAC) is ~$0.37/resource-hour billed monthly above the free tier (~$50/user/month for the Team edition equivalent). Self-hosted state via Azure Blob removes the SaaS cost. |
| **Operational shape** | One Python class per environment shape. Onboarding a new client is `pulumi up -s client-N`. State is per stack. |

### Why not the alternatives

| Alternative | Why not (here) |
|---|---|
| **Terraform (HCL)** | Same Azure provider quality, larger ecosystem. The deciding factor is *language*: Helix's per-client logic (conditional Private Link for high-sensitivity clients, iterating over variable VM lists, computing DCR transformations from a typed config) is awkward in HCL — `for_each` + `dynamic` blocks read poorly past a certain complexity. Python expresses the same thing in straight code. |
| **OpenTofu** | Identical reasoning to Terraform. Plus: Helix already runs Pulumi for the simulation infrastructure; introducing a second IaC tool fragments the deployment story for marginal benefit. |
| **Bicep / ARM** | Free, native, no provider drift. But: no cross-cloud (Helix has AWS components), weaker abstraction story than Pulumi's `ComponentResource`, and harder to do the "client baseline as a Python package" pattern this architecture relies on. |
| **Crossplane** | Excellent for GitOps-driven multi-cluster Kubernetes. Wrong shape for one-shot per-tenant onboarding. |
| **CDKTF** | Solves the HCL-ergonomics problem but inherits Terraform's state model; Pulumi is a tighter integration if you're starting fresh with a Python team. |

### Cost / operational impact vs Terraform specifically

| Dimension | Pulumi (Python) | Terraform (HCL) |
|---|---|---|
| State backend | Pulumi Cloud (paid above free tier) or self-hosted (free) | Terraform Cloud / S3 / Azure Blob — same options |
| Per-engineer learning curve | Python (already known by team) | HCL (small but additional language) |
| Conditional logic | Native Python | `count` / `for_each` / `dynamic` |
| Component reuse | Class with typed inputs | Modules with variables |
| Testing | `pytest` against unit-tested resources | Terratest (Go) or `terraform test` |
| Net assessment | Better fit for a per-client provisioning pattern in a Python-first team | Better fit for organisations standardised on HCL with large module libraries |

### Trade-offs accepted

- Smaller ecosystem of community modules than Terraform Registry. Mitigated by the Azure provider being first-class and Python's package ecosystem covering most utility needs.
- Pulumi Cloud is a SaaS dependency unless self-hosted. The brief's threat model already trusts Azure — adding Pulumi Cloud is a small additional surface; self-hosting state in Azure Blob is the conservative option and is the recommendation here.

---

## 5. ⏳ Workflow Orchestration — Temporal

### Decision summary

| | |
|---|---|
| **Choice** | Temporal workflows (already used by the simulation engine) drive the onboarding pipeline. |
| **Alternatives considered** | GitHub Actions · Azure DevOps Pipelines · Argo Workflows · AWS Step Functions · Airflow · Prefect |
| **Cost shape** | Self-hosted Temporal: free OSS + cluster cost (already paid by the simulation engine). Temporal Cloud: pay per action (~$25 per million actions). |
| **Operational shape** | One worker pool runs both simulation and onboarding workflows. New steps are Python activities. |

### Why not the alternatives

| Alternative | Why not (here) |
|---|---|
| **GitHub Actions** | Right tool for code-triggered CI/CD pipelines; wrong tool for long-lived stateful workflows that wait on external signals (M365 admin consent can take 48 hours). Re-running a failed step from scratch is fine for builds; for partial provisioning it can leave half-deployed Azure state. |
| **Azure DevOps Pipelines** | Same shape as GitHub Actions. No advantage if GitHub is already the source of truth. |
| **Argo Workflows** | Kubernetes-native; would require running a Kubernetes cluster solely to orchestrate onboarding — disproportionate for a small team. |
| **Step Functions** | AWS-native; cross-cloud orchestration adds latency and an extra IAM/Entra federation layer for no functional benefit. |
| **Airflow / Prefect** | Designed for scheduled DAGs (data pipelines), not durable state machines waiting on human-in-the-loop signals. |

### The deciding property

Temporal's **durable execution** model is the only one in the list that handles the M365-consent step natively: the workflow can wait days for an external signal, survive worker restarts, and resume from the exact step that paused — without bespoke retry/state code. Every alternative would require rebuilding that capability.

---

## 6. 📡 Application Telemetry — OpenTelemetry

### Decision summary

| | |
|---|---|
| **Choice** | OpenTelemetry SDK in application code; OTel Collector exports to Azure Monitor's Logs Ingestion API via DCR. |
| **Alternatives considered** | Application Insights SDK · Datadog APM · New Relic · Splunk OpenTelemetry distribution (SignalFx) · Honeycomb |
| **Cost shape** | OTel SDKs are free; cost is in the destination (Azure Monitor / LAW). No per-host APM license. |
| **Operational shape** | Standard SDK in each service. Collector is one container, deployed as ACA sidecar or shared. |

### Why not the alternatives

| Alternative | Why not (here) |
|---|---|
| **Application Insights SDK (classic)** | Native to Azure but **vendor-locks the instrumentation itself**. Migrating off Application Insights later would require touching every service. OTel decouples *what's emitted* from *where it goes*, which preserves optionality. |
| **Datadog APM / New Relic / Honeycomb** | Best-in-class APM UX, but: (a) per-host or per-tenant pricing scales badly across N client environments; (b) sends application telemetry out of the federated boundary; (c) duplicates the security stack's identity model with their own. |
| **Splunk OTel distribution (SignalFx)** | Still OTel under the hood — no fundamental difference at the SDK layer. Adopting the upstream OTel SDK avoids vendor-flavoured forks. |

### Trade-offs accepted

- Azure Monitor's OTel support is via the Logs Ingestion API and does not (yet) cover every OTel signal as richly as a purpose-built APM. Distributed-trace UX in Azure Monitor is improving but lags Datadog/Honeycomb. Acceptable for a security-first platform; revisit if APM becomes a primary use case.

---

## 7. 🖥️ VM Log Collection — Azure Monitor Agent (AMA)

### Decision summary

| | |
|---|---|
| **Choice** | Azure Monitor Agent + Data Collection Rules on every Windows / Linux VM in the client tenant. |
| **Alternatives considered** | Microsoft Monitoring Agent (MMA / OMS) · Fluent Bit · Vector · Logstash / Beats · Splunk Universal Forwarder · Cribl Edge |
| **Cost shape** | AMA is free; charges are downstream LAW ingestion. Configuration is centralised in DCRs (one DCR per source class, attached to many VMs). |
| **Operational shape** | Deployed by Azure Policy `DeployIfNotExists` — every VM in the client subscription receives AMA automatically without inventory tracking. |

### Why not the alternatives

| Alternative | Why not (here) |
|---|---|
| **MMA / OMS legacy agent** | Microsoft is retiring MMA. Choosing it now is choosing a dead-end migration. |
| **Fluent Bit / Vector** | Excellent agents with rich processing; their flexibility is a *liability* in a multi-tenant baseline because per-VM configuration drift is exactly what we're trying to eliminate. AMA + DCR centralises config — change a DCR once, every attached VM picks it up. Fluent Bit configuration would need to live in the Pulumi module per shape and be redistributed per change. |
| **Splunk Universal Forwarder** | Pairs naturally with Splunk; redundant with Sentinel's collection model. |
| **Cribl Edge** | Powerful processing-at-source, but adds a vendor + license + a layer of routing logic for a problem DCR transformations already solve at ingestion. |

### Trade-offs accepted

- AMA's processing logic is less expressive than Fluent Bit's. Mitigated because heavy transformation belongs in DCR transformations (KQL), not at the agent — keeping the agent dumb is intentional.
- AMA is Azure-only. Linux VMs in AWS use OTel + Logs Ingestion API instead (already the path for application logs).

---

## 8. 🌐 Edge / WAF Logs — Cloudflare Logpush

### Decision summary

| | |
|---|---|
| **Choice** | Cloudflare Logpush → Azure Blob Storage → DCR-based Logs Ingestion → LAW |
| **Alternatives considered** | Cloudflare GraphQL Analytics API (pull-based) · Cloudflare Logpull · A self-built collector polling Cloudflare's API · Cribl |
| **Cost shape** | Logpush itself is included in Cloudflare Enterprise (or available as an add-on); Azure cost is Blob storage (cents) + LAW ingestion. |
| **Operational shape** | One-time Logpush job configuration per Cloudflare zone; thereafter zero ops. |

### Why not the alternatives

| Alternative | Why not (here) |
|---|---|
| **GraphQL / Logpull (pull-based)** | Requires building and operating a poller with rate-limit handling, batching, retries, and gap detection. Logpush is push-based and gap-detected by Cloudflare itself. |
| **Self-built collector** | Re-invents Logpush at higher operational cost. |
| **Cribl** | Useful if heavy transformation or multi-destination routing is needed. Not needed here — DCR transformations on the LAW side cover the routing. |

### Trade-offs accepted

- Logpush is a Cloudflare Enterprise feature. If Helix's Cloudflare plan changes, the fallback is the GraphQL API path with the operational cost noted above.

---

## 9. ⚙️ Drift Correction — Azure Policy `DeployIfNotExists`

### Decision summary

| | |
|---|---|
| **Choice** | Azure Policy assignments deployed at the client subscription scope, evaluated continuously inside the client tenant. |
| **Alternatives considered** | Pulumi-only reconciler running on a schedule · Custom drift detector + remediator · Crossplane compositions · Azure Resource Graph queries with custom remediation |
| **Cost shape** | Azure Policy is **free**. Remediation tasks consume normal Azure operations. |
| **Operational shape** | Policy runs natively inside each client tenant — no Helix-side worker is on the critical path. |

### Why not the alternatives

| Alternative | Why not (here) |
|---|---|
| **Pulumi-only reconciler** | Requires Helix-side orchestration to run on a schedule for every client tenant — back to the cross-tenant exposure problem Lighthouse limits. Policy lives *inside* the client and self-enforces. |
| **Custom drift detector** | Re-implements what Policy already does, with more code to maintain. |
| **Crossplane** | Inappropriate weight class for the problem. |

### Why Policy *and* Pulumi (not either/or)

Pulumi handles the **shape** of the environment (workspace, DCRs, Sentinel enablement). Policy handles **continuous coverage** of resources that appear after onboarding (a new VM provisioned by the client six months later). They cover different time horizons of the same problem.

---

## 📌 Summary — Where Lock-in Was Accepted, and Where It Wasn't

| Layer | Lock-in level | Why we accepted (or didn't) |
|---|---|---|
| **SIEM (Sentinel)** | High | Worth the lock-in for Entra/M365 integration and operational simplicity at small-team scale. |
| **Log store (LAW)** | High | Coupled to Sentinel by necessity. Mitigated by Archive-tier export-on-restore. |
| **Cross-tenant identity (Lighthouse)** | High | The architecture *is* this lock-in. No equivalent multi-cloud abstraction exists. |
| **IaC (Pulumi)** | Medium | Code is portable to Terraform with effort; component shapes survive the translation. |
| **Workflow (Temporal)** | Medium | Already a platform standard at Helix; durable-execution semantics are hard to replicate. |
| **Application telemetry (OpenTelemetry)** | **Deliberately low** | OTel was chosen *because* it preserves the option to change backends later. |
| **VM agent (AMA)** | Medium | Azure-only, but the alternative (Fluent Bit + per-VM config) is more lock-in to *operational complexity* even though the agent itself is portable. |

The pattern: **lock-in was accepted at layers where Microsoft's first-party integration is the differentiator**, and **deliberately avoided at the layer (instrumentation) where the choice is most reversible and most likely to need to change**.

---

[← Risks](08-risks.md) &nbsp;|&nbsp; Next: [Appendix →](appendix.md)

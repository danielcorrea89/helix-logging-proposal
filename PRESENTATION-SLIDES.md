---
marp: true
theme: default
paginate: true
style: |
  :root {
    --bg: #0f172a;
    --surface: #1e293b;
    --accent: #38bdf8;
    --accent2: #818cf8;
    --text: #e2e8f0;
    --muted: #64748b;
    --success: #4ade80;
    --warning: #fb923c;
    --danger: #f87171;
  }
  section {
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    padding: 52px 72px;
  }
  h1 { color: var(--accent); font-size: 2em; margin-bottom: 0.2em; }
  h2 { color: var(--text); font-size: 1.5em; margin-top: 0; }
  h3 { color: var(--muted); font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 0.4em; }
  strong { color: var(--accent); }
  em { color: var(--muted); font-style: normal; }
  ul { margin: 0.5em 0; }
  li { margin: 0.35em 0; font-size: 0.95em; }
  li li { font-size: 0.88em; color: var(--muted); margin: 0.2em 0; }
  table { width: 100%; border-collapse: collapse; font-size: 0.78em; }
  th { background: var(--surface); color: var(--accent); padding: 9px 14px; text-align: left; }
  td { padding: 7px 14px; border-bottom: 1px solid var(--surface); }
  tr:last-child td { border-bottom: none; }
  code { background: var(--surface); color: var(--accent); padding: 2px 7px; border-radius: 4px; font-size: 0.9em; }
  pre { background: var(--surface); padding: 20px; border-radius: 8px; border-left: 3px solid var(--accent); }
  blockquote { border-left: 3px solid var(--accent); padding-left: 20px; color: var(--muted); margin: 1em 0; }
  footer { color: var(--muted); font-size: 0.65em; }
  header { color: var(--muted); font-size: 0.68em; text-transform: uppercase; letter-spacing: 0.1em; }
  section::after { color: var(--muted); font-size: 0.65em; }

  section.title {
    justify-content: flex-end;
    background: linear-gradient(160deg, #0f172a 55%, #1e3a5f 100%);
    padding-bottom: 80px;
  }
  section.title h1 { font-size: 3em; border-bottom: 2px solid var(--accent); padding-bottom: 14px; }
  section.title h2 { color: var(--muted); font-weight: 300; font-size: 1.2em; }
  section.title p { color: var(--muted); font-size: 0.85em; margin-top: 2em; }

  section.statement {
    justify-content: center;
    align-items: center;
    text-align: center;
    background: linear-gradient(160deg, #0f172a 60%, #1a1f35 100%);
  }
  section.statement h2 { font-size: 2em; line-height: 1.5; max-width: 85%; }
  section.statement p { color: var(--muted); font-size: 1em; margin-top: 1em; }

  section.warning-slide {
    background: linear-gradient(160deg, #0f172a 60%, #2d1515 100%);
  }
  section.warning-slide h1 { color: var(--warning); }
  section.warning-slide strong { color: var(--warning); }

  section.principle {
    justify-content: center;
    background: linear-gradient(160deg, #0f172a 50%, #0f2335 100%);
  }
  section.principle h1 { font-size: 2.6em; border: none; }
  section.principle h2 { font-size: 1.3em; color: var(--muted); font-weight: 300; }

  .pill-row { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 1em; }
  .pill { background: var(--surface); color: var(--accent); padding: 5px 14px; border-radius: 20px; font-size: 0.8em; border: 1px solid var(--accent); display: inline-block; }
  .pill-warn { background: var(--surface); color: var(--warning); padding: 5px 14px; border-radius: 20px; font-size: 0.8em; border: 1px solid var(--warning); display: inline-block; }
  .divider { border: none; border-top: 1px solid var(--surface); margin: 1.2em 0; }
---

<!-- _class: title -->
<!-- _paginate: false -->

# 🔐 Helix
## Logging Platform Architecture Proposal

*Cross-tenant telemetry · Zero standing access · Automated at scale*

---

<!-- _class: statement -->

## Before this is a logging problem —
## it's a **cross-tenant trust problem**

*N isolated client tenants · separate Entra directories · three different audiences*

<!--
TALKING POINTS
- Resist the urge to open with "we're going to talk about logging"
- The hard part isn't collecting logs — it's the topology
- Each client is a completely separate Azure Entra directory
- Any solution that ignores this either leaks data between clients, or requires permanent privileged access to every tenant
- Both are non-starters for a cybersecurity platform
- Set up why federated is the obvious answer before showing a diagram
-->

---

<!-- _header: The Problem -->

# 📡 Three sources. Three audiences. One constraint.

<br>

| Sources | Audiences |
|---|---|
| Shared AWS — Cloudflare · Django · Containers | **Developers** — platform debugging only |
| Shared Azure — Simulation Engine · Entra · ACA | **IT Admins / Security** — cross-env visibility |
| Client tenants — Windows · Linux · NVA · M365 | **Clients** — their own data only |

<br>

> These three audiences must **never share the same access boundary**

<!--
TALKING POINTS
- Three structurally different source types — each needs a different collection path
- Three audiences with completely different access needs
- Developers must not see client security events
- Clients must not see each other's data
- Admins need cross-env visibility but with accountability for every query
- The access separation is not optional — it's the design constraint everything else serves
-->

---

<!-- _header: Architecture -->

# 🏗️ Architecture Overview

```mermaid
flowchart LR
    subgraph aws["Shared — AWS ☁️"]
        CF[Cloudflare]
        DJ[Django / OTel]
    end
    subgraph az["Shared — Azure ⚙️"]
        SE["Simulation Engine\nTemporal + OTel"]
        ACA[Container Apps]
    end
    subgraph ct["Client Tenants 🔒  —  data stays here"]
        SRCC["Windows · Linux · NVA · M365"]
        CLAWS[("Per-Client LAW")]
        SRCC -- "AMA + DCR" --> CLAWS
    end
    subgraph helix["Helix Managing Tenant 🏢"]
        SLAW[("Shared LAW")]
        SENT["Sentinel · Workbooks"]
        SLAW --> SENT
    end
    CF & DJ -- "OTel / Logpush" --> SLAW
    SE & ACA -- "OTel / Diagnostics" --> SLAW
    SENT -. "Lighthouse + PIM\nread-only · audited\ndata never moves" .-> CLAWS
```

<!--
TALKING POINTS
- Walk left to right — sources, collection, storage, access
- Two separate storage destinations: Shared LAW for Helix-owned stuff, per-client LAW for client data
- The dotted line is the most important: Sentinel QUERIES OUT — data never physically moves into Helix's tenant
- Client logs stay in the client's Azure environment, always
- Pause here for initial questions — people will have them
-->

---

<!-- _class: principle -->

# Collect locally
# Govern centrally
# **Access selectively**

<!--
TALKING POINTS
- This is the design stance in one line — say it out loud
- Collect locally = data never leaves the tenant it belongs to
- Govern centrally = one Sentinel, one Workbook layer, one place to manage rules and alerts
- Access selectively = JIT elevation, time-limited, every query audited
- Every architecture decision flows from this principle
- If you forget everything else, remember this
-->

---

<!-- _header: Architecture -->

# 🎯 Five decisions that drive everything

| Decision | Choice | Wrong choice costs you |
|---|---|---|
| Collection model | **Federated** — logs stay in tenant | One credential breach → all clients exposed |
| Workspace topology | **One LAW per client** | RBAC gap leaks data across clients |
| Cross-tenant access | **Lighthouse + PIM/JIT** — no standing privilege | Blast radius that never closes |
| IaC pattern | **Pulumi ComponentResource** — baseline as a class | Silent drift by client 10 |
| Log classification | **Three tiers** — Analytics · Basic · Archive | Paying Sentinel prices for debug noise |

<!--
TALKING POINTS
- Read the left column only — the decisions
- For each: say the choice, then what the wrong choice costs
- These are load-bearing — change any one and the architecture changes materially
- The rest of the presentation is justification for each of these
- Don't dwell here — this is a map, not the territory
-->

---

<!-- _header: Security -->

# 🚧 Three trust boundaries

```mermaid
flowchart TB
    subgraph managing["Helix Managing Tenant 🏢"]
        SENT["Sentinel / Workbooks"]
        PIM["Azure PIM — no standing privilege"]
    end
    crossing["── cross-tenant boundary ──"]
    subgraph ca["Client Tenant A 🔒"]
        LAWA[("LAW — Client A")]
        VMSA["VMs · NVA → Log Forwarder · M365"]
        VMSA --> LAWA
    end
    subgraph cn["Client Tenant N 🔒"]
        LAWN[("LAW — Client N")]
        VMSN["VMs · NVA → Log Forwarder · M365"]
        VMSN --> LAWN
    end
    PIM -. "JIT elevation · time-limited" .-> crossing
    crossing -. "Lighthouse · read-only · audited" .-> LAWA & LAWN
    LAWA & LAWN -. "delegated query" .-> SENT
```

<!--
TALKING POINTS
- Boundary 1: Helix's own tenant — standard Azure RBAC, least privilege, PIM for privileged roles
- Boundary 2: The high-risk one — cross-tenant. Lighthouse + PIM is the only crossing point
- Boundary 3: Inside each client tenant — Pulumi-deployed DCRs, AMA, NSG rules, consistent baseline
- The architecture is designed so Boundary 2 is the only place where identity risk concentrates
- And we've minimised that risk deliberately
-->

---

<!-- _header: Security -->

# ⏱️ How cross-tenant access actually works

```mermaid
sequenceDiagram
    actor A as Helix Admin
    participant P as Azure PIM
    participant L as Lighthouse
    participant C as Client LAW
    participant AL as Audit Log

    A->>P: Request activation — state justification
    P->>A: MFA required
    P-->>A: Role active · 4-hour window
    P->>AL: Who · why · when — immutable

    A->>L: Query client workspace
    L->>C: Delegated read · read-only
    C-->>A: Data returned
    L->>AL: Query logged — tables accessed

    Note over P,C: Auto-expires — no manual revocation
```

<!--
TALKING POINTS
- No standing access — every single query requires this flow
- MFA at activation, not just at login
- Every activation AND every query is logged immutably
- The 4-hour window is the default — configurable per policy
- Access auto-expires, nothing to forget to revoke
- Pre-activate at shift start if you're expecting a live incident
- Full chain of custody in both Helix and client Entra audit logs
-->

---

<!-- _class: warning-slide -->
<!-- _header: Security — Honest Assessment -->

# ⚠️ Blast radius — honest

<br>

**Worst case:** credential compromised + MFA bypassed

<br>

| What they can do | What they cannot do |
|---|---|
| Read all clients' log data | Modify or delete any data |
| For up to **4 hours** | Access compute, network, identity |
| Fully audited | Extend beyond the PIM window |

<br>

> Compare to centralised: **unlimited · permanent · no audit · no expiry**

<!--
TALKING POINTS
- Don't hide this — say it clearly and frame it correctly
- The blast radius is: all clients' log data, read-only, 4 hours, fully audited
- That's the design — bounded by construction, not by luck
- The comparison is what matters: centralised model has no time limit, no per-client isolation, no automatic expiry
- Federated is the harder operational model and the materially safer breach model
- This is why we pay the 15% workspace cost premium
-->

---

<!-- _header: Automation -->

# 🚀 Onboarding — one command, one baseline

```mermaid
flowchart LR
    A(["New tenant 🆕"]) --> B["Create Azure Tenant"]
    B --> C["Deploy Simulation Infra"]
    C --> D["Deploy Logging Baseline\nWorkspace · DCRs · Policy\nLighthouse · Sentinel"]
    D --> E["Wait: M365 consent\nclient admin · one-time"]
    E --> F{"Verify ingestion\nAMA · Policy · M365"}
    F -->|Pass| G["Issue client access\nRBAC + Workbooks in client tenant"]
    G --> H(["Environment Active ✅"])
    F -->|Fail| I["Alert + retry\nup to 3 attempts"]
    I -.-> D
```

<!--
TALKING POINTS
- Every client gets the same baseline through the same code path
- No manual steps — no portal clicks, no per-client configuration
- M365 consent is the one human step — client's Global Admin must click approve — workflow dispatches the URL and waits up to 48 hours
- Verification gate: AMA heartbeat + Policy compliance + M365 connector active
- If verification fails: 3 retries with backoff, then platform team is paged
- The environment is not released until logging is verified
-->

---

<!-- _header: Automation -->

# 🤖 Temporal — not just another pipeline

<br>

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 40px;">
<div>

### GitHub Actions
*Delivery pipeline*

- Triggered by repo events
- Short-lived jobs
- Re-run if it fails
- Great for: build · test · deploy

</div>
<div>

### Temporal
*Durable orchestration*

- Triggered by platform events
- Survives restarts · crashes
- Resumes from last state
- Great for: provision · wait · retry over days

</div>
</div>

<br>

> M365 consent can wait **48 hours** — that's not a CI/CD job

<!--
TALKING POINTS
- Both are called "workflows" — very different problems
- GitHub Actions: repo event automation, ephemeral, pipeline thinking
- Temporal: durable stateful processes, resumes after crash, wait for external signals
- The onboarding process has a 48-hour wait built in (M365 consent)
- Retries can span hours. Workers can restart mid-provisioning.
- GitHub Actions is wrong tool for this. Temporal is the right one.
- We use GitHub Actions for CI/CD (Pulumi deployments, drift checks) — correct use
-->

---

<!-- _header: Cost Model -->

# 💰 Not all logs are equal

<br>

| Tier | Cost | Retention | Use for |
|---|---|---|---|
| **Analytics** | ~$2.30 / GB | 90 days hot | Security events · audit logs · product events |
| **Basic** | ~$0.50 / GB | 8 days hot | Verbose app logs · container output · debug traces |
| **Archive** | ~$0.02 / GB / mo | Up to 12 years | Compliance retention · historical forensics |

<br>

> **DCR transformations** route at ingestion — filtered data is never stored, never charged

<!--
TALKING POINTS
- Default flat ingestion = paying Analytics prices for everything, including debug noise nobody queries
- DCR transforms route before data lands — most cost-effective lever available
- Security events: Analytics. Container stdout: Basic. Old compliance data: Archive.
- 80% cost reduction per GB moving from Analytics to Basic
- Archive at $0.02/GB is effectively free for compliance retention
-->

---

<!-- _header: Cost Model -->

# ⚖️ Isolated vs shared — the numbers

<br>

**10 clients · 10 GB/day each · approx. USD**

| | Log Analytics | Sentinel | **Monthly total** |
|---|---|---|---|
| 10 isolated workspaces | ~$6,900 | ~$7,380 | **~$14,280** |
| 1 shared workspace | ~$5,880 | ~$6,300 | **~$12,180** |
| Difference | | | **~$2,100 / month (+15%)** |

<br>

**What the 15% buys:**
- Data never co-located across clients
- Bounded blast radius if credential compromised
- Clean per-client audit trail
- Per-client retention policies

<!--
TALKING POINTS
- The cost difference is real — don't pretend it isn't
- Roughly $2,100/month at 10 clients
- But frame what it buys: data residency, bounded blast radius, clean audit, flexible retention
- For any regulated client (defence, government, financial services) — isolated workspaces are likely non-negotiable regardless of cost
- Shared workspace remains a viable lower-cost tier option for clients where isolation is a preference, not a hard requirement
- The billing lands in each client's Azure subscription — if Helix manages those subscriptions, it flows through service pricing
-->

---

<!-- _header: Team Impact -->

# 👥 What changes for each team

| Team | They gain | Upfront ask |
|---|---|---|
| **Infrastructure** | Repeatable onboarding pattern — one Pulumi run per client | Workspace topology decisions at design time |
| **DevOps** | Policy self-heals coverage gaps — no manual tracking | Build the Pulumi component · DCRs · Sentinel rule library |
| **Security — Blue** 🔵 | Full audit trail · Sentinel across all clients · JIT access | PIM activation adds 2–5 min to first query |
| **Security — Red** 🔴 | Consistent telemetry — gaps visible via Policy compliance | Validate detection coverage per client onboarding |
| **Business / Finance** | Per-client cost attribution via tags | Agree billing model at onboarding contract |
| **Operations** | Single Workbook layer across all clients | Maintain query packs · alert triage runbooks |
| **Software Dev** | Structured traces without elevated cloud permissions | Integrate OTel SDK into Django + Temporal workers |

<!--
TALKING POINTS
- Don't read the table — scan the "They gain" column, let each team self-identify
- Then call out the upfront asks explicitly — don't hide them
- DevOps: several engineering weeks before first client onboarded — one-time investment
- Blue team: PIM latency is a deliberate trade-off, not a bug — pre-activate at shift start
- Software Dev: OTel integration is real code, not a config toggle — one-time, ongoing as new services added
- Give each team space to respond here — this is where conversation happens
-->

---

<!-- _header: Risks -->

# ⚠️ Risk landscape

```mermaid
quadrantChart
    title Likelihood vs Impact
    x-axis Low Likelihood --> High Likelihood
    y-axis Low Impact --> High Impact
    quadrant-1 Prioritise
    quadrant-2 Mitigate
    quadrant-3 Monitor
    quadrant-4 Watch
    Lighthouse Compromise: [0.15, 0.95]
    Client Data Challenge: [0.15, 0.80]
    Cost Explosion: [0.50, 0.80]
    Inconsistent Onboarding: [0.45, 0.72]
    Sentinel Cost Growth: [0.25, 0.55]
    NVA Format Issues: [0.50, 0.42]
    M365 Coverage Gaps: [0.45, 0.42]
    AWS Log Latency: [0.20, 0.35]
    Pulumi State Drift: [0.25, 0.35]
    AMA NVA Compat: [0.45, 0.20]
```

<!--
TALKING POINTS
- Lighthouse compromise sits top-left: low probability, critical impact — deliberate placement
- The mitigations (PIM/JIT, scoped delegation, hardened managing tenant) are designed to keep it there
- Cost explosion and inconsistent onboarding are the medium-probability risks — both directly addressed by the architecture
- M365 coverage gaps and NVA format issues are medium probability, medium impact — documented and mitigated
- Key message: we know where the risks are, we've designed for them, the residual is acceptable
-->

---

<!-- _header: Risks -->

# 🛡️ Residual risk — acceptable by design

<br>

| Concern | Federated (this proposal) | Centralised (alternative) |
|---|---|---|
| Credential compromise | Read-only · all clients · **4 hours** | Read-only · all clients · **unlimited** |
| Data residency breach | Client data stays in client tenant | All clients co-located |
| Blast radius | Bounded by PIM window + scope | Unbounded |
| Audit trail | Immutable · per-client | Commingled |

<br>

> The federated model is the harder operational posture and the **materially safer breach posture**

<!--
TALKING POINTS
- The residual risk profile is acceptable for a cybersecurity simulation platform
- The dominant risks — Lighthouse blast radius, cost explosion — are both mitigated below equivalent risks in the alternative architectures
- Close by naming the trade-off honestly: operational complexity is higher, breach containment is significantly better
- Then hand it to the room — "What questions does the team have?"
-->

---

<!-- _class: statement -->
<!-- _paginate: false -->

## Centralise **control**.
## Centralise **visibility**.
## Never centralise **risk**.

*Full proposal · diagrams · implementation detail → github.com/danielcorrea89/helix-logging-proposal*

<!--
TALKING POINTS
- End on the design principle, not on a risk slide
- Invite questions — don't rush to close
- Have the docs open in browser tabs for any deep dives
- The proposal is all on GitHub — they can read it after the call
-->

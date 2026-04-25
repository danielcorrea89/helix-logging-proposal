# Helix — Logging Platform Architecture Proposal

**Created by:** Daniel Correa &nbsp;|&nbsp; **Date:** April 2026 &nbsp;

---

Helix's platform spans shared AWS and Azure infrastructure alongside N isolated per-client Azure tenants. Before this is a logging problem, it is a **cross-tenant identity and trust problem**. A solution that collects everything without designing trust boundaries first creates security debt that compounds with every client onboarded.

This proposal recommends a **federated collection model with centralised governance**: logs are collected and stored inside each client's own Entra boundary; Helix retains authorised, auditable visibility across all environments through carefully scoped, time-limited delegation. Three alternatives were evaluated — the recommendation and the reasoning behind it are in [Options](docs/02-options.md).

> [!IMPORTANT]
> **Design stance** — Centralise observability *control* and *search experience*. Do not centralise *risk*. Collect locally, govern centrally, access selectively.

---

## Architecture Overview

```mermaid
flowchart LR
    subgraph aws["Shared — AWS"]
        CF[Cloudflare]
        DJ[Django / Python]
        AWSC[Containers]
    end

    subgraph aze["Shared — Azure"]
        SE["Simulation Engine · Temporal"]
        ACA["Container Apps · Entra ID"]
    end

    subgraph ct["Client Tenants — data stays here · never leaves"]
        SRCC["Windows · Linux · NVA · M365"]
        CLAWS[("Per-Client LAW\none per tenant")]
        SRCC -- "AMA + DCR\nPurview connector" --> CLAWS
    end

    subgraph helix["Helix Managing Tenant"]
        SLAW[("Shared LAW")]
        SENTINEL["Microsoft Sentinel\nWorkbooks · Analytics"]
        SLAW --> SENTINEL
    end

    subgraph who["Who accesses what"]
        DEV["Developers\nLog Analytics Reader\nShared LAW — platform tables only"]
        SEC["IT Admins · Security\nPIM/JIT elevation required\nSentinel — shared + all client workspaces"]
        CLI["Clients\nLog Analytics Reader\nin their own tenant\nWorkbooks deployed at onboarding"]
    end

    CF -- "Logpush" --> SLAW
    DJ -- "OTel SDK" --> SLAW
    AWSC -- "Firehose" --> SLAW
    SE & ACA -- "OTel · Diagnostics" --> SLAW

    SLAW --> DEV
    SENTINEL --> SEC
    SENTINEL -. "Lighthouse delegation\nPIM/JIT required · read-only · audited\nSentinel queries out — data never moves" .-> CLAWS
    CLAWS --> CLI
```

---

## How This Addresses Each Requirement

| Requirement | Technology chosen | How |
|---|---|---|
| **All key systems captured** | Azure Monitor Agent, DCRs, OTel SDK, Cloudflare Logpush, Purview connector, Azure Policy | Dedicated ingestion path per source type; Azure Policy auto-deploys collection to new resources without manual intervention |
| **Least privilege access** | Azure Lighthouse, Azure PIM/JIT, per-workspace RBAC | No standing cross-tenant access; JIT elevation required for every admin query; each persona scoped to only their data |
| **Not cumbersome for admins** | Microsoft Sentinel, Azure Workbooks, cross-workspace KQL | Single Sentinel instance surfaces all environments; no per-tenant portal login; standardised query packs cover common investigations |
| **Automated, maintainable by a small team** | Pulumi (Python), Temporal, Azure Policy | Client baseline is one Pulumi component instantiation; Policy self-heals coverage gaps; logging is a mandatory workflow step — never skipped |
| **Flexible and scalable** | Pulumi ComponentResource, Azure Policy, ACA scale-to-zero | Adding a client is a Pulumi run; Policy covers new resources automatically; idle environments cost near-zero |
| **Cost effective** | Log Analytics tiers (Analytics / Basic / Archive), DCR transformations | Logs routed to cheapest appropriate tier at ingestion; security events in Analytics, verbose logs in Basic |

---

## Five Decisions That Drive Everything

| Decision | Choice | The wrong choice costs you |
|---|---|---|
| **Collection model** | Federated — logs stay in each tenant | Centralising raw data means one compromised Helix credential exposes every client simultaneously |
| **Workspace topology** | One Log Analytics Workspace per client | A shared workspace with misconfigured RBAC leaks one client's security events to another |
| **Cross-tenant access** | Azure Lighthouse + PIM/JIT — no standing privilege | Permanent cross-tenant admin access is a blast radius that never closes |
| **IaC pattern** | Pulumi Python `ComponentResource` — client baseline as a class | Copy-paste configs drift silently; by client 10 every environment is slightly different |
| **Log classification** | Three tiers: Analytics · Basic · Archive | Flat ingestion means paying Sentinel-tier prices for debug output nobody ever queries |

---

## Security at the Cross-Tenant Boundary

The most important security property of this architecture is that **no Helix user has standing read access to any client workspace**. Every cross-tenant query is JIT-elevated, time-limited, and fully audited.

```mermaid
sequenceDiagram
    actor Admin as Helix Admin
    participant PIM as Azure PIM
    participant LH as Lighthouse
    participant CLAW as Client LAW
    participant AL as Entra Audit Log

    Admin->>PIM: Request Log Analytics Reader — state justification
    PIM->>Admin: Require MFA + approval
    Admin->>PIM: MFA satisfied
    PIM-->>Admin: Role active · 4-hour window (default)
    PIM->>AL: Record — who · why · duration

    Admin->>LH: Query client workspace
    LH->>CLAW: Delegated read · read-only scope
    CLAW-->>Admin: Data returned
    LH->>AL: Record — query executed · tables accessed

    Note over PIM,CLAW: Access auto-expires — no manual revocation needed
    Note over AL: Immutable audit trail in both Helix and client Entra tenants
```

> [!WARNING]
> **Lighthouse blast radius is bounded by design.** A compromised Helix credential that also bypasses MFA can read all clients' log data for at most 4 hours. It cannot modify data, access resources outside Log Analytics, or escalate beyond the delegated read scope. This is the primary reason the architecture uses federated workspaces rather than a shared central store — the wrong model turns a credential compromise into a full data breach across every client with no time limit and no audit trail.

---

## Onboarding a New Client

Every client environment gets the same logging baseline through the same code path. There are no manual steps.

```mermaid
flowchart TD
    START(["New client tenant"])

    T1["Create Azure Tenant\nor accept existing credentials"]
    T2["Deploy Simulation Infrastructure\npulumi up — helix/simulation/client-N"]
    T3["Deploy Logging Baseline\nClientLoggingBaseline — Pulumi ComponentResource\nWorkspace · DCRs · Policy · Lighthouse · Sentinel"]
    T4{"Verify Ingestion\nAMA heartbeat · Policy compliance\nM365 connector active"}
    T5["Issue Client Access\nRBAC + Workbooks deployed in client tenant\nclient notified with portal URL"]
    ERR["Alert — Onboarding Incomplete\nplatform team notified"]
    END(["Environment Active\nlogging live · client access granted"])

    START --> T1 --> T2 --> T3 --> T4
    T4 -->|"Pass"| T5 --> END
    T4 -->|"Fail"| ERR -. "retry with backoff" .-> T3
```

> [!NOTE]
> Logging is not a separate onboarding task — it is a mandatory step in the same automated workflow that provisions the simulation environment. A client environment cannot be marked ready without a verified logging baseline. See [Automation](docs/07-automation.md) for the implementation detail.

---

## Explore the Full Proposal

| # | Section | What it covers |
|---|---|---|
| 1 | [Requirements](docs/01-requirements.md) | Problem decomposition, personas, success criteria as design constraints, assumptions |
| 2 | [Options](docs/02-options.md) | Three architectural options with data-flow diagrams, comparison matrix, recommendation |
| 3 | [Architecture](docs/03-architecture.md) | Ingestion paths per source, workspace topology, access model, technology choices |
| 4 | [Security Controls](docs/04-security.md) | Trust boundaries, Lighthouse blast radius, PIM/JIT, pipeline identity model, Policy enforcement |
| 5 | [Team Impact](docs/05-team-impact.md) | Layer ownership, impact narrative across Infrastructure, DevOps, Security, Business, Ops, Dev |
| 6 | [Cost Model](docs/06-cost-model.md) | Log tier routing, per-client attribution, isolated vs shared comparison, scale-to-zero |
| 7 | [Automation](docs/07-automation.md) | Pulumi ComponentResource pattern, Temporal integration, policy-as-code, drift detection |
| 8 | [Risks & Mitigations](docs/08-risks.md) | Risk matrix, register, Lighthouse blast radius deep dive, residual risk acceptance |
| — | [Implementation Appendix](docs/appendix.md) | Pulumi component code, Temporal activity detail, pipeline identity model — low-level reference |

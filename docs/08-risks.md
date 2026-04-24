[← Home](../README.md)

# 8 — Risks and Mitigations

## Risk Matrix

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
    Sentinel Cost Growth: [0.25, 0.55]
    AWS Log Latency: [0.20, 0.35]
    Pulumi State Drift: [0.25, 0.35]
    Cost Explosion: [0.50, 0.80]
    Inconsistent Onboarding: [0.45, 0.72]
    NVA Format Issues: [0.50, 0.42]
    M365 Coverage Gaps: [0.45, 0.42]
    AMA NVA Compat: [0.45, 0.20]
```

> Lighthouse Compromise sits in the top-left — low probability, critical impact. The mitigations (PIM/JIT, scoped delegation, hardened managing tenant) are specifically designed to keep it there.

---

## Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Lighthouse / managing tenant credential compromise | Low | Critical | PIM/JIT — no standing access; narrow delegation scope (LAW read only); hardened managing tenant; break-glass separation |
| 2 | Cost explosion from verbose simulation log ingestion | Medium | High | DCR filtering before ingestion; Basic Logs tier for verbose tables; budget alerts per client; archive after retention window |
| 3 | Inconsistent client onboarding creates logging gaps | Medium | High | Pulumi `ComponentResource` — all clients get same baseline; Policy `DeployIfNotExists` fills gaps for new resources; Temporal workflow enforces logging as a gate |
| 4 | NVA log format inconsistency across Fortinet/pfSense versions | Medium | Medium | Standardise on CEF output format; log forwarder VM normalises before AMA; test per NVA model during client onboarding validation |
| 5 | M365 Purview connector coverage gaps | Medium | Medium | Document which M365 audit tables are available per licence tier; set client expectations at onboarding; supplement with Entra sign-in logs where M365 audit is incomplete |
| 6 | AWS → Azure log latency unacceptable for real-time use | Low | Medium | OTel path (near-real-time) for application logs; Kinesis Firehose path (minutes latency) is infrastructure-only — document the SLO boundary; no use case in the brief requires sub-minute AWS log delivery |
| 7 | Client challenges Helix's access to their log data | Low | High | Lighthouse audit log provides complete chain of custody; PIM activation record shows who accessed what and why; access is time-limited and revocable by the client; contractual access terms defined at onboarding |
| 8 | Pulumi state drift in long-lived client environments | Low | Medium | Weekly `pulumi refresh` in CI; Azure Policy continuous compliance evaluation; drift surfaced as PR diff for review |
| 9 | AMA not supported on some NVA operating systems | Medium | Low | NVAs use syslog forwarding to a dedicated Linux log forwarder VM — AMA is only required on the forwarder, not the NVA itself |
| 10 | Sentinel cost grows faster than expected at scale | Low | Medium | Sentinel is only enabled on the Shared LAW and on client workspaces for high-sensitivity tiers; standard-tier clients use Azure Monitor alerting only — evaluate Sentinel per client based on value |

---

## Deep Dive: Risk 1 — Lighthouse Blast Radius

This is the only risk in the register that is both low probability and catastrophic in its potential impact. It deserves more than a table entry.

**Scenario:** A Helix platform engineer's account is compromised. The attacker activates the PIM-eligible Lighthouse delegation role and gains read access to a client's Log Analytics Workspace.

**What they can see:** That client's security events, authentication logs, M365 audit trail, and NVA logs for the duration of the PIM window (maximum 4 hours).

**What they cannot do:**
- Access other clients' workspaces (delegation is scoped per workspace, per client)
- Delete or modify log data (delegation is read-only)
- Access the client tenant's compute, network, or identity resources (delegation does not extend to those scopes)
- Extend their access beyond the PIM window without a new activation (which generates another audit event)

**Why this is an acceptable residual risk:** The blast radius is bounded by design. This is not a "one credential → all clients' raw data" scenario. A compromise is contained to one client's workspace for at most 4 hours, and the access is fully audited. Compare this to Option B (fully centralised), where a single workspace compromise exposes all clients' raw data with no time limit.

**Hardening steps beyond those already described:**
- Enable Microsoft Entra ID Protection on the managing tenant — compromised credential detection fires before an attacker can activate PIM
- Require MFA hardware token (FIDO2) for PIM activation, not TOTP
- Alert on PIM activation outside business hours
- Periodic access review of the PIM-eligible group membership — remove anyone who no longer needs it

---

## Risk Acceptance Summary

The residual risk profile of the recommended architecture is acceptable for a cybersecurity simulation platform. The dominant risks (Lighthouse blast radius, cost explosion) are both mitigated to a level where the probability × impact product is lower than the equivalent risks in the alternative architectures:

- Option B (centralised) has higher blast radius impact with equivalent or lower mitigation options
- Option C (security-only centralisation) has lower cost risk but higher operational complexity and gap risk

The federated model with PIM/JIT and Policy enforcement is the most defensible operating posture for this platform.

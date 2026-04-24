[← Home](../README.md) &nbsp;|&nbsp; [← Cost Model](06-cost-model.md) &nbsp;|&nbsp; Next: [Risks →](08-risks.md)

# 7 — Automation

## Design Principle

A logging platform that requires manual steps to onboard each client tenant will not scale. The onboarding of a new client's logging baseline must be a **code execution**, not a project. Every configuration decision made once must apply everywhere, consistently, without drift.

---

## Why Pulumi in Python

Helix already uses Pulumi as its IaC platform of choice. Python enables the client logging baseline to be expressed as a reusable class — instantiated with client-specific parameters, not copied and modified per deployment. This is the difference between a **platform** and a collection of scripts.

DSL-based tools (Terraform HCL, Bicep) require workarounds like `for_each` with complex dynamic blocks to express conditional logic. In Python, the client baseline class can:
- Branch on client tier (standard vs high-sensitivity)
- Iterate over a list of VM resource IDs to attach DCRs
- Conditionally enable Private Link based on client configuration
- Register the Lighthouse delegation only after confirming the client has deployed the ARM template
- Return typed outputs that downstream Temporal workflows can consume

---

## Pulumi Component Architecture

```python
# Client logging baseline — one instantiation per client tenant
class ClientLoggingBaseline(pulumi.ComponentResource):
    """
    Provisions the complete logging baseline for one client tenant:
      - Log Analytics Workspace (isolated, per-client)
      - Data Collection Rules for Windows, Linux, and CEF sources
      - Azure Policy assignments (diagnostic settings, AMA enforcement)
      - Lighthouse registration (read delegation to Helix PIM group)
      - Sentinel enablement and M365 connector configuration
      - RBAC: client reader group scoped to this workspace
    """
    def __init__(self, client_id: str, config: ClientConfig, opts=None):
        super().__init__("helix:logging:ClientLoggingBaseline", client_id, {}, opts)
        # workspace, dcrs, policy, lighthouse, sentinel...


class SharedPlatformLogging(pulumi.ComponentResource):
    """
    Provisions Helix's shared observability layer:
      - Shared Log Analytics Workspace
      - Microsoft Sentinel
      - Cloudflare Logpush DCR
      - OTel ingestion endpoint
      - Entra diagnostic settings
      - Standard workbooks and query packs
    """


class AwsLogForwarder(pulumi.ComponentResource):
    """
    Configures the AWS → Azure log forwarding path:
      - Kinesis Firehose delivery stream → Azure Blob Storage
      - DCR to process Firehose output on ingestion
      - OTel Collector configuration for Django/Python services
    """
```

Each class encodes the full set of decisions for its domain. A new engineer onboarding a client runs one command:

```python
# main.py — client onboarding stack
baseline = ClientLoggingBaseline(
    client_id="acme-corp",
    config=ClientConfig(
        subscription_id="...",
        location="australiaeast",
        tier="standard",          # or "high-sensitivity" for isolated Private Link
        vm_resource_ids=[...],
        m365_tenant_id="...",
    )
)
```

`pulumi up` provisions the workspace, DCRs, policy assignments, and Lighthouse delegation. No manual steps. No portal clicks.

---

## Onboarding Pipeline

```mermaid
flowchart TD
    START(["New Client Tenant"])
    T1["Create Azure Tenant\nor accept existing credentials"]
    T2["Deploy Simulation Infrastructure\npulumi up — helix/simulation/client-N"]
    T3["Deploy Logging Baseline\npulumi up — helix/logging/client-N\nClientLoggingBaseline component"]
    T3B["Request M365 Consent\ngenerate consent URL · dispatch to client admin\nblocks up to 48h for client action"]
    T4{"Verify Ingestion\nAMA heartbeat · Policy compliant\nM365 connector active?"}
    T5["Issue Client Access\nRBAC + Workbooks deployed in client tenant\nclient notified with portal URL"]
    ERR["Alert: Onboarding Incomplete\nplatform team notified"]
    RETRY["Auto-retry correctable gaps\nor manual intervention for structural drift"]
    END(["Environment Active\nlogging live · client access granted"])

    START --> T1 --> T2 --> T3 --> T3B --> T4
    T4 -->|"Pass"| T5 --> END
    T4 -->|"Fail"| ERR --> RETRY
    RETRY -.-> T3
```

New client environments at Helix are provisioned through a Temporal workflow (the simulation engine already uses Temporal for orchestration). The logging baseline is a step in that workflow — not a separate manual process.

```
Temporal Workflow: provision-client-environment
  ├── Activity: create_azure_tenant (or accept existing)
  ├── Activity: deploy_simulation_infrastructure (existing Pulumi stack)
  ├── Activity: deploy_logging_baseline          ← ClientLoggingBaseline
  │   └── pulumi up helix/logging/client-{id}
  ├── Activity: request_m365_consent             ← generate consent URL; send to client admin
  │   └── blocks until client confirms or 48-hour timeout (manual step — requires client action)
  ├── Activity: verify_log_ingestion             ← AMA heartbeat + M365 connector active check
  └── Activity: notify_client_ready              ← confirm RBAC + Workbooks deployed in client tenant; send client the portal URL
```

**M365 consent step:** The M365 Defender/Purview connector requires the client's M365 Global Administrator to grant delegated consent to Helix's Sentinel managed application. This cannot be automated — it requires a human action in the client's tenant. The `request_m365_consent` activity generates the consent URL and dispatches it to the client contact on record. The workflow blocks with a Temporal `heartbeat` signal until the client confirms consent or the timeout expires, at which point the platform team is alerted. Clients who skip this step have full Azure log collection but no M365 audit ingestion.

This integration means logging is never an afterthought. Every client environment that exists has a logging baseline. There is no configuration drift between environments because the same code path runs for every client.

---

## Policy as Code

Azure Policy assignments are deployed by the Pulumi onboarding module, not applied manually in the portal. Two policy effects are used:

**`DeployIfNotExists`** — used for diagnostic settings on Azure resources. If a new Azure resource (VM, storage account, key vault) appears in the client subscription without a diagnostic setting pointing to the client LAW, Azure Policy deploys one automatically within minutes. The Pulumi pipeline does not need to track individual resource additions.

**`AuditIfNotExists`** — used as a compliance gate for AMA presence on VMs. The compliance API is polled by the Temporal workflow's `verify_log_ingestion` activity. A non-compliant VM blocks the workflow from marking the environment as ready.

Policy definitions are stored in the Pulumi repository as JSON/Python objects — version-controlled, reviewable, and deployed consistently across all client subscriptions.

---

## Dashboard and Query Packs as Code

Workbooks and saved KQL queries are deployed as Pulumi resources (ARM template outputs or `azure-native.operationalinsights.SavedSearch`). This means:

- A new detection query written by the security team is deployed to all client workspaces on the next pipeline run
- Workbook changes are reviewed via pull request before deployment
- There is no manual "export from portal, import elsewhere" workflow
- Rollback is `pulumi destroy` on the affected resource

Standard query packs cover the three personas:
- **Client pack:** product event tables, simulation lifecycle events
- **Developer pack:** request traces, error rates, latency percentiles, ACA scaling events
- **Security pack:** authentication events, privilege escalation patterns, NVA deny trends, M365 anomalies

---

## Sentinel Analytics Rule Lifecycle

Sentinel analytics rules are deployed to all client workspaces as code. This creates a lifecycle management responsibility: a misconfigured or noisy rule deployed once affects every client simultaneously.

**Deployment model:**
- Rules are stored in the Pulumi repository as Python/JSON objects under `helix/logging/sentinel_rules/`
- All rule changes go through a pull request — no direct portal edits
- The Pulumi pipeline deploys rule changes to a single test client workspace first; promotion to all client workspaces requires explicit approval in the pipeline

**Rule coverage by tier:**

| Rule set | Standard tier | High-sensitivity tier |
|---|---|---|
| Authentication anomalies (brute force, impossible travel) | Included | Included |
| Privilege escalation patterns | Included | Included |
| Lateral movement detection (Windows Event correlation) | Included | Included |
| NVA deny trend analysis | Included | Included |
| M365 admin activity anomalies | Included | Included |
| Custom SOAR playbooks (auto-contain, notify) | Not included | Included |
| Extended threat hunting rules | Not included | Included |

**Tuning:** False-positive suppression (watchlists, exclusion rules) is maintained per client. A suppression added for one client does not affect others — each client has isolated suppression state. Rule version history is tracked via git; rollback is `git revert` + pipeline run.

---

## Drift Detection

After initial onboarding, the logging baseline can drift if resources are added or configurations changed manually. Two mechanisms detect and correct drift:

1. **Azure Policy continuous compliance:** Evaluated every 24 hours. Non-compliant resources are reported in the Azure Policy compliance dashboard and can trigger automated remediation tasks.

2. **Pulumi refresh in CI:** A scheduled pipeline run executes `pulumi refresh` weekly against each client stack. Drift between Pulumi state and actual Azure state is surfaced as a diff. For diffs that match known correctable patterns (e.g. a DCR association missing from a new VM), the pipeline auto-applies the correction and raises a notification. For structural drift (e.g. a workspace retention setting changed), the diff is raised as a pull request for platform team review.

These two mechanisms together mean that a client environment that has been modified post-onboarding is detected and brought back to baseline. Azure Policy handles the continuous self-healing of resource-level gaps; Pulumi handles workspace-level configuration drift. Neither requires manual per-tenant audit.

---

[← Cost Model](06-cost-model.md) &nbsp;|&nbsp; Next: [Risks →](08-risks.md)

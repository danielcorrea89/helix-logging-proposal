[← Home](../README.md) &nbsp;|&nbsp; [← Decisions](09-decisions.md)

# Implementation Appendix

This appendix contains low-level implementation detail referenced from the main proposal sections. It is not required reading to understand the architecture — it exists for engineers who will build or review the implementation.

---

## Pulumi Component Architecture

Three Pulumi `ComponentResource` classes encode the full set of infrastructure decisions for each domain. Each is instantiated once per environment — there is no copy-paste.

```python
# Client logging baseline — one instantiation per client tenant
class ClientLoggingBaseline(pulumi.ComponentResource):
    """
    Provisions the complete logging baseline for one client tenant:
      - Log Analytics Workspace (isolated, per-client, in client's own tenant)
      - Data Collection Rules for Windows, Linux, and CEF/syslog sources
      - Azure Policy assignments (diagnostic settings, AMA enforcement)
      - Lighthouse registration (read delegation to Helix PIM group)
      - Microsoft Sentinel enablement and M365 connector configuration
      - RBAC: client reader group + Workbooks deployed in client's own tenant
    """
    def __init__(self, client_id: str, config: ClientConfig, opts=None):
        super().__init__("helix:logging:ClientLoggingBaseline", client_id, {}, opts)
        # workspace, dcrs, policy, lighthouse, sentinel, rbac, workbooks...


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

**Client onboarding instantiation:**

```python
baseline = ClientLoggingBaseline(
    client_id="acme-corp",
    config=ClientConfig(
        subscription_id="...",
        location="australiaeast",
        tier="standard",          # or "high-sensitivity" for Private Link + extended detection
        vm_resource_ids=[...],
        m365_tenant_id="...",
    )
)
```

`pulumi up` provisions the workspace, DCRs, policy assignments, Lighthouse delegation, Sentinel, and client RBAC. No manual steps.

---

## Temporal Workflow — Activity Detail

New client environments are provisioned through a Temporal workflow. The logging baseline is one activity in that workflow.

```
Temporal Workflow: provision-client-environment
  ├── Activity: create_azure_tenant
  │   └── accept existing subscription or create new tenant
  ├── Activity: deploy_simulation_infrastructure
  │   └── pulumi up helix/simulation/client-{id}
  ├── Activity: deploy_logging_baseline          ← ClientLoggingBaseline
  │   └── pulumi up helix/logging/client-{id}
  ├── Activity: request_m365_consent
  │   └── generate consent URL → dispatch to client admin contact
  │       blocks on Temporal signal until client confirms (48h timeout)
  │       clients who skip: full Azure log collection, no M365 ingestion
  ├── Activity: verify_log_ingestion
  │   └── AMA heartbeat received? Policy compliant? M365 connector active?
  └── Activity: notify_client_ready
      └── RBAC + Workbooks deployed in client tenant → send portal URL to client
```

---

## Pipeline Identity Model

Each pipeline identity is scoped to exactly one job. No identity holds more permission than its single purpose requires. No pipeline identity can read log data.

| Identity | Purpose | Scope | Auth method |
|---|---|---|---|
| `id-shared-logging-deploy` | Deploy shared LAW, Sentinel, workbooks | `Contributor` on Shared LAW resource group | Workload Identity Federation (GitHub Actions / Pulumi Cloud → Entra OIDC) |
| `id-client-onboard` | Deploy Lighthouse registration + DCRs + Policy in client tenant | `Contributor` on client LAW resource group + `Resource Policy Contributor` on client subscription (via Lighthouse) | Workload Identity Federation |
| `id-client-read` (PIM group) | Query client workspaces for operational/incident use | `Log Analytics Reader` on client LAW (via Lighthouse) | Human PIM activation — not a pipeline identity |
| `id-ama-deploy` | Install AMA on client VMs | `Virtual Machine Contributor` on VM resource group | Workload Identity Federation |

No identity has `Owner`, `Subscription Contributor`, or `Global Admin` by default. The Pulumi pipeline never reads log data — only deploys collection infrastructure.

---

## Hardened Managing Tenant — Control Detail

| Control | Implementation |
|---|---|
| No permanent privileged roles | All `Owner`, `Contributor`, `Security Admin` assignments are PIM-eligible only |
| Conditional Access on admin paths | Require MFA + compliant device + named location for all PIM activations |
| Separate admin identities | Platform operators use a separate cloud-only admin account — not their day-to-day identity |
| Break-glass accounts | Two emergency-access accounts with permanent `Global Admin`, excluded from Conditional Access, MFA hardware-bound, credentials in physical safe, alert on any use |
| No client secrets in pipelines | All pipeline auth uses Workload Identity Federation (OIDC) — no long-lived secrets |

---

## Per-Source Log Tier Assignment

DCR transformation rules route each log category to its tier at ingestion, before data lands in any table.

| Log source | Tier | Rationale |
|---|---|---|
| Windows Security Events (4624, 4625, 4648, 4672, 4720…) | Analytics | Core authentication and privilege events — high query frequency |
| Windows Event — verbose (application, system) | Basic | Useful during incidents; not routinely queried |
| Linux auth / syslog (auth, sudo, SSH) | Analytics | Authentication and privilege escalation signals |
| Linux syslog — verbose (cron, daemon, kernel) | Basic | Low value outside active investigation |
| NVA — deny / IPS / VPN events | Analytics | Network security decisions — queried in blue team exercises |
| NVA — allow / statistics / flow | Basic | High volume, low value unless investigating lateral movement |
| M365 audit (admin activity, Purview, Defender) | Analytics | Compliance and security — queried for audit and investigation |
| Django / Python application logs | Basic | Platform debugging — high volume, queried only during incidents |
| ACA container logs | Basic | High volume simulation output — useful during dev/debug |
| Cloudflare access logs | Basic | High volume; WAF blocks routed to Analytics via DCR filter |
| Cloudflare WAF blocks and bot events | Analytics | Actionable security signals — small volume, high value |
| Entra sign-in and audit logs | Analytics | Identity events — always relevant for security posture |
| GitHub Actions / Pulumi Cloud audit | Basic | Deployment audit trail — queried during security investigations |

---

[← Decisions](09-decisions.md) &nbsp;|&nbsp; [↑ Home](../README.md)

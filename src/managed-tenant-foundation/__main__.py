import uuid
import pulumi
import pulumi_azure_native as azure_native
from pulumi_azure_native import resources
from pulumi_azure_native import operationalinsights
from pulumi_azure_native import managedservices

config = pulumi.Config("helix")
location = config.get("location") or "australiaeast"

# deployed by managing tenant, TenantID and GroupID shared with client tenant for delegation
managing_tenant_id = config.require("managingTenantId")
reader_group_object_id = config.require("readerGroupObjectId")
reader_group_display_name = config.get("readerGroupDisplayName") or "helix-lighthouse-readers"

client_config = azure_native.authorization.get_client_config()
managed_subscription_id = client_config.subscription_id
scope = f"/subscriptions/{managed_subscription_id}"
reader_role_definition_id = "acdd72a7-3385-48ef-bd42-f606fba81ae7" # Azure built-in role: Reader

rg = resources.ResourceGroup(
    "rg-helix-lab-client-a",
    resource_group_name="rg-helix-lab-client-a",
    location=location,
)

law = operationalinsights.Workspace(
    "law-helix-client-a",
    resource_group_name=rg.name,
    workspace_name="law-helix-client-a",
    location=rg.location,
    sku=operationalinsights.WorkspaceSkuArgs(
        name="PerGB2018",
    ),
    retention_in_days=30,
)

registration_definition_id = str(uuid.uuid4())
registration_assignment_id = str(uuid.uuid4())

registration_definition = managedservices.RegistrationDefinition(
    "helix-lighthouse-reader-definition",
    registration_definition_id=registration_definition_id,
    scope=scope,
    properties=managedservices.RegistrationDefinitionPropertiesArgs(
        registration_definition_name="Helix Lighthouse Reader Delegation",
        description="Minimal Helix/Xintra lab delegation from customer-simulated tenant to managing tenant.",
        managed_by_tenant_id=managing_tenant_id, #lighthouse delegation from customer tenant to managing tenant
        authorizations=[
            managedservices.AuthorizationArgs(
                principal_id=reader_group_object_id,
                principal_id_display_name=reader_group_display_name,
                role_definition_id=reader_role_definition_id,
            )
        ],
    ),
)

registration_assignment = managedservices.RegistrationAssignment(
    "helix-lighthouse-reader-assignment",
    registration_assignment_id=registration_assignment_id,
    scope=scope,
    properties=managedservices.RegistrationAssignmentPropertiesArgs(

        registration_definition_id=registration_definition.id,
    ),
)

pulumi.export("managed_subscription_id", managed_subscription_id)
pulumi.export("resource_group_name", rg.name)
pulumi.export("log_analytics_workspace_name", law.name)
pulumi.export("registration_definition_id", registration_definition.id)
pulumi.export("registration_assignment_id", registration_assignment.id)
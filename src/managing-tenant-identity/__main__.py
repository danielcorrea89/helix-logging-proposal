"""An Azure RM Python Pulumi program"""

import pulumi
import pulumi_azuread as azad

config = pulumi.Config("helix")

# Your @gmail user's Entra object ID.
# Keep this as config so the lab is explicit and repeatable.
operator_user_object_id = config.require("operatorUserObjectId")

reader_group = azad.Group(
    "helix-lighthouse-readers",
    display_name="helix-lighthouse-readers",
    security_enabled=True,
)

reader_membership = azad.GroupMember(
    "helix-lighthouse-readers-operator-user",
    group_object_id=reader_group.object_id,
    member_object_id=operator_user_object_id,
)

pulumi.export("reader_group_object_id", reader_group.object_id)
pulumi.export("reader_group_display_name", reader_group.display_name)
# ---------------------------------------------------------------------------
# Module: fabric-connection
# Creates a Microsoft Fabric Connection (preview resource).
#
# NOTE: This resource requires preview mode enabled in the fabric provider
# configuration: preview = true
# ---------------------------------------------------------------------------

resource "fabric_connection" "this" {
  display_name      = var.display_name
  connectivity_type = var.connectivity_type
  privacy_level     = var.privacy_level

  connection_details = {
    type            = var.connection_details.type
    creation_method = var.connection_details.creation_method
    parameters      = var.connection_details.parameters
  }

  credential_details = {
    credential_type       = var.credential_type
    connection_encryption = var.connection_encryption
    single_sign_on_type   = "None"
    skip_test_connection  = var.skip_test_connection
  }
}

# ---------------------------------------------------------------------------
# Module: fabric-shortcuts
# Creates Microsoft Fabric OneLake Shortcuts.
#
# Shortcuts are virtual references that point to data stored in external
# locations (ADLS Gen2, S3, GCS) or other OneLake items. They appear as
# folders in a Lakehouse but involve no data copy — queries read directly
# from the target storage.
#
# Provider resource: fabric_shortcut (microsoft/fabric >= 1.8, PREVIEW)
# NOTE: This resource requires preview mode enabled in the provider config.
# ---------------------------------------------------------------------------

# ---- ADLS Gen2 Shortcut: External weather data feed -----------------------
resource "fabric_shortcut" "adls_gen2" {
  for_each = var.adls_gen2_shortcuts

  workspace_id = var.workspace_id
  item_id      = var.lakehouse_id
  name         = each.value.name
  path         = each.value.path

  target = {
    adls_gen2 = {
      location      = each.value.location
      subpath       = each.value.subpath
      connection_id = each.value.connection_id
    }
  }
}

# ---- OneLake (cross-workspace) Shortcuts -----------------------------------
resource "fabric_shortcut" "onelake" {
  for_each = var.onelake_shortcuts

  workspace_id = var.workspace_id
  item_id      = var.lakehouse_id
  name         = each.value.name
  path         = each.value.path

  target = {
    onelake = {
      workspace_id = each.value.target_workspace_id
      item_id      = each.value.target_item_id
      path         = each.value.target_path
    }
  }
}

# ---- Amazon S3 Shortcuts (commented out — enable when partner data ready) --
#
# resource "fabric_shortcut" "amazon_s3" {
#   for_each = var.s3_shortcuts
#
#   workspace_id = var.workspace_id
#   item_id      = var.lakehouse_id
#   name         = each.value.name
#   path         = each.value.path
#
#   target = {
#     amazon_s3 = {
#       location      = each.value.location     # e.g. "https://partner-bucket.s3.us-east-1.amazonaws.com"
#       subpath       = each.value.subpath       # e.g. "/contoso/shared-catalog"
#       connection_id = each.value.connection_id
#     }
#   }
# }

variable "display_name" {
  description = "The display name of the Fabric Deployment Pipeline (max 246 characters)."
  type        = string
}

variable "description" {
  description = "The description of the Fabric Deployment Pipeline (max 256 characters)."
  type        = string
  default     = ""
}

variable "stages" {
  description = <<-EOT
    Ordered list of deployment pipeline stages (min 2, max 10).
    Each stage defines a promotion target. Stages are evaluated in order
    (first = source, last = production).

    - display_name: Stage label (e.g. "Development", "Test", "Production")
    - description:  Stage purpose / notes
    - is_public:    Whether the stage is publicly visible
    - workspace_id: (Optional) Fabric Workspace ID to assign to this stage.
                    Leave null to assign later via the Fabric portal.
  EOT
  type = list(object({
    display_name = string
    description  = string
    is_public    = bool
    workspace_id = optional(string)
  }))

  validation {
    condition     = length(var.stages) >= 2 && length(var.stages) <= 10
    error_message = "A deployment pipeline must have between 2 and 10 stages."
  }
}

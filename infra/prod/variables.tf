variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "westeurope"
}

variable "org_prefix" {
  description = "Organization prefix"
  type        = string
  default     = "pnb-dlb"
}

variable "env_short" {
  description = "Short environment code"
  type        = string
  default     = "p"
}

variable "project" {
  description = "Project name"
  type        = string
  default     = "pnballie"
}

variable "image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

variable "vm_size" {
  description = "Azure VM size"
  type        = string
  default     = "Standard_B1s"
}

variable "vm_admin_username" {
  description = "Linux admin username for VM"
  type        = string
  default     = "pnballie"
}

variable "vm_ssh_public_key" {
  description = "SSH public key for VM admin user"
  type        = string

  validation {
    condition     = length(trimspace(var.vm_ssh_public_key)) > 0
    error_message = "vm_ssh_public_key must be provided and cannot be empty."
  }
}

variable "ssh_allowed_cidr" {
  description = "CIDR allowed to SSH to the VM"
  type        = string
  default     = "0.0.0.0/0"
}

variable "data_disk_size_gb" {
  description = "Managed data disk size in GB for persistent app data"
  type        = number
  default     = 16
}

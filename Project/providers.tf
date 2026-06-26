terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = "sps"

  default_tags {
    tags = {
      Project     = "sps" # canonical: Project is "sps" platform-wide (supersedes var.project = "sps-staffing")
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
  # Vertical is set per-resource (shared | staffing | edtech | itservice), not as a default tag.
}

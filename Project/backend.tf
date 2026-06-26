terraform {
  backend "s3" {
    bucket         = "sps-staffing-tfstate-412058343855"
    key            = "global/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "sps-staffing-tflock"
    encrypt        = true
    profile        = "sps"
  }
}

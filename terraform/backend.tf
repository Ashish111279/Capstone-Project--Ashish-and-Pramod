terraform {
  backend "s3" {
    key          = "capstone/terraform.tfstate"
    use_lockfile = true
  }
}
locals {
  distro_list = flatten([
    for distro, emails in var.email_object : [
      "\"${distro}\": {\"L\": [ ${join(",", formatlist("{\"S\": \"%s\"}", emails))} ]}"
    ]
  ])
  distro_list_string = join(",", local.distro_list)
}

data "template_file" "test" {
  template = "${file("${path.module}/table_layout.json")}"
  vars = {
    account_name = "test123"
    distro_list  = "${local.distro_list_string}"
  }
}

resource "aws_dynamodb_table_item" "email_distro" {
  table_name = var.table_name
  hash_key   = var.hash_key

  item = data.template_file.test.rendered
}
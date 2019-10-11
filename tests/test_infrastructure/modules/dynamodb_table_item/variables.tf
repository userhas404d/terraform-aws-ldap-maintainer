
variable "email_object" {
  default = {
    "Distro1" : ["user1", "user2"],
    "Distro2" : ["user2", "user3"]
  }
}

variable "hash_key" {
  type = string
}

variable "table_name" {
  type = string
}
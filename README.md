# Terraform AWS LDAP Maintainer

*NOTE:* THIS IS A WORK IN PROGRESS

A step function to maintain LDAP users via slack.

## ToDo

- [ ] LDAP query should be able to send queries and perform actions
  
- [ ] determine how to validate the user
    - get group members from a target security group and check the user's email against them? would require the slack library in slack-listener to query the user's email address
    - lock the integration to a specific channel?

### Final steps

- [ ] document, test, and write the layer creation step
- [ ] make sure this thing is scheduled to run (cloudwatch event w/ stepfunction target)
- [ ] create a drawing of this monstrosity
- [ ] code cleanup

### Done

- [x] Configure asynchronous invocation of the backend lambda function
- [x] "are you sure" pop ups
- [x] give user feedback when button is pressed.. (this should come from slack-listener)

## Overview

1. get the users that are going to be disabled
2. send that list to the next lambda function that will..
    1. send the list to slack with an approve/deny button
    2. if approved, take action on users
    3. if denied, do nothing

## Setup

1. Retrieve the LDAPS endpoint of your target AD deployment.

    **Note:** This can be accomplished via SimpleAD by creating an ALB that listens via TLS on port 636 and forwards to your SimpleAD A record

1. Within your LDAP directory..
   1. create a new OU called `DisabledUsers`
   2. Create a user that will be used by the lambda function
2. Populate an *encrypted* ssm parameter with the user's password

enable slack events for your slackbot

**Note**: there's a quirk with lambda permissions and the api gateway endpoint associated with the slack-listener function that forces you to create the required lambda permissions _manually_

1. got to https://api.slack.com
2. find your app
3. navigate to Features > Event Subscriptions > Enable Events
4. enter the api gateway url created in the previous step

## References

- The [AD Schema](https://docs.microsoft.com/en-us/windows/win32/adschema/active-directory-schema)
- Bobbie Couhbor's awesome [blogpost](https://blog.kloud.com.au/2018/01/09/replacing-the-service-desk-with-bots-using-amazon-lex-and-amazon-connect-part-3/) on using python-ldap via lambda
- Rigel Di Scala's blog post [Write a serverless Slack chat bot using AWS](https://chatbotslife.com/write-a-serverless-slack-chat-bot-using-aws-e2d2432c380e)

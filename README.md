# Terraform AWS LDAP Maintainer

*NOTE:* THIS IS A WORK IN PROGRESS

A step function to maintain LDAP users via slack.

## ToDo

- [ ] implement test toggle for disabling users
- [ ] implement autodocstring across functions
- [ ] populate ldap with user emails
- [ ] run through an end to end test
- [ ] create screen capture of workflow
- [ ] conditionally deploy a windows instance into the test simplead env with AD tools installed
- [ ] s3 objects should be deleted after 30 days
- [ ] determine how to validate the user
    - get group members from a target security group and check the user's email against them? would require the slack library in slack-listener to query the user's email address
    - lock the integration to a specific channel?

### Final steps

- [ ] document, test, and write the layer creation step
- [ ] make sure this thing is scheduled to run (cloudwatch event w/ stepfunction target)
- [ ] create a drawing of this monstrosity
- [ ] code cleanup

### Done

- [x] move username list to terraform
- [x] store initial slack response in s3 so sfn events don't become bloated
- [x] LDAP query should be able to send queries and perform actions
- [x] add user's email to ldap_query's results
- [x] Add list of hands off accounts to ldap
- [x] Message time stamp should be from the right time zone
- [x] [UPDATE](https://api.slack.com/methods/chat.update) the original message based on user inputs.
- [x] Configure asynchronous invocation of the backend lambda function
- [x] "are you sure" pop ups
- [x] give user feedback when button is pressed.. (this should come from slack-listener)

## Overview

This project deploys a collection of lambda functions, an api endpoint, and a step function that will automate disabling LDAP users via an interactive slack message.

## Setup

1. Retrieve the LDAPS endpoint of your target AD deployment.

    **Note:** This can be accomplished via SimpleAD by creating an ALB that listens via TLS on port 636 and forwards requests to your SimpleAD A record. See the associated [AWS blog post](https://aws.amazon.com/blogs/security/how-to-configure-an-ldaps-endpoint-for-simple-ad/) or the tests of this project for a reference architecture.

2. Within your LDAP directory create a user that will be used by the lambda function. This user will need permissions to query LDAP and disable users.
3. Populate an *encrypted* ssm parameter with this new user's password and use the key value as the input for `svc_user_pwd_ssm_key` variable.
4. Enable slack events for your slackbot
   1. got to https://api.slack.com
   2. find your app
   3. navigate to Features > Event Subscriptions > Enable Events
   4. enter the api gateway url created in the previous step

## Architecture



## References

- The [AD Schema](https://docs.microsoft.com/en-us/windows/win32/adschema/active-directory-schema)
- Bobbie Couhbor's awesome [blogpost](https://blog.kloud.com.au/2018/01/09/replacing-the-service-desk-with-bots-using-amazon-lex-and-amazon-connect-part-3/) on using python-ldap via lambda
- Rigel Di Scala's blog post [Write a serverless Slack chat bot using AWS](https://chatbotslife.com/write-a-serverless-slack-chat-bot-using-aws-e2d2432c380e)

# weather-notifications

This Lambda cron runs every morning and sends an email because I'm bad at looking at the weather app

## What do you need

* [Pulumi CLI](https://www.pulumi.com/docs/get-started/install/)
* AWS Credentials that are allowed to provision the infrastructure
* AWS CLI
* Python3.7 or higher installed on your computer

## Build it

Here are the steps to build this project. Make sure that you have installed the requirements to do these commands.

1. Clone the repo
2. Sign up for a free [weatherapi.com](weatherapi.com) account. Make sure you have an API Key
3. Add in your desired email in the environment variable *SNS_EMAIL*, the zip code for the weather into *WEATHER_NOTIFICATION_ZIP_CODE*, and weather API key in *WEATHER_API_KEY*
4. Run *pulumi up*, review the infrastructure being created, then select *yes*
5. Once the stack is completely built, you will get an email from AWS asking you to opt-in to alerts from the newly created SNS target. Accept it so you will receive alerts later
6. After the infrastructure has been provisioned, you can go into the AWS console or invoke the Lambda from the AWS CLI
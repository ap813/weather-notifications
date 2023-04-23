import boto3
import os
import requests
import json

# AWS clients to interact with services
secrets_manager = boto3.client('secretsmanager', region_name="us-west-2")
sns = boto3.client('sns', region_name="us-west-2")

# Base URL for weather API
weather_endpoint = "https://api.weatherapi.com/v1/forecast.json"

# See if api key secret is valid
def validate_secret(secret):
    if not secret:
        raise Exception(f"Failed to get secret from {os.environ['SECRET_ID']} version {os.environ['SECRET_VERSION']}")

    api_key = secret['SecretString']

    if not api_key:
        raise Exception("Get secret from secrets manager, but there is no value")
    
    return api_key

# Call weather API and return response body
def get_weather_data(secret):
    # Get API url parameters
    api_key = validate_secret(secret)
    zip_code = os.environ.get('ZIP_CODE')

    # Construct and send request for weather data
    # Only need to get today's forecast
    weather_url = f"{weather_endpoint}?key={api_key}&q={zip_code}&days=1"
    headers = {'content-type': 'application/json'}
    resp = requests.get(weather_url,headers=headers)
    return resp.json()

def validate_data(json):
    if not json['forecast']:
        raise Exception("weather data didn't have forecast")
    if not json['forecast']['forecastday']:
        raise Exception("weather data didn't have forecastday")
    if not type(json['forecast']['forecastday']) == list:
        raise Exception("forecastday doesn't have the correct data in it")
    if len(json['forecast']['forecastday']) == 0:
        raise Exception("forecastday has length of 0")
    return

class WeatherData:
    minF = 0
    maxF = 0
    rainning_chance = 0

    def __init__(self, minF, maxF, rainning_chance):
        self.minF = minF
        self.maxF = maxF
        self.rainning_chance = rainning_chance

    # Look at rain chance and give an appropriate message
    def rain_message(self):
        if self.rainning_chance > 50:
            return "It will probably rain"
        elif self.rainning_chance > 20:
            return "It will probably not rain"
        elif self.rainning_chance > 0:
            return "There is a small chance it could rain"
        else:
            return "There will be no rain today"


# Analyze the weather data
def analyze_data(json):
    validate_data(json)
    
    # Create a WeatherData object with all of the important info
    weather_today = json['forecast']['forecastday']
    return WeatherData(
        minF=weather_today[0]['day']['mintemp_f'],
        maxF=weather_today[0]['day']['maxtemp_f'],
        rainning_chance=weather_today[0]['day']['daily_chance_of_rain']
    )

# Construct message for SMS
def create_message(weather_data):
    return f"""The min temp today is {weather_data.minF} and the max temp today is {weather_data.maxF}. {weather_data.rain_message()}."""

# Entry point for lambda call
def lambda_handler(event, context):
    # Pull API Key
    api_key_secret = secrets_manager.get_secret_value(
        SecretId=os.environ.get('SECRET_ID'),
        VersionId=os.environ.get('SECRET_VERSION')
    )

    # Pull weather data from API
    data = get_weather_data(api_key_secret)

    # Parse the API response
    weather_data = analyze_data(data)

    # Send the SMS message
    sns.publish(
        TopicArn=os.environ.get('TOPIC_ARN'),
        Message=json.dumps({
            "default": create_message(weather_data),
        }),
        MessageStructure='json'
    )
import json
import boto3
import os
from datetime import datetime, timedelta

# AWS Clients
bedrock_client = boto3.client("bedrock-runtime")
cost_explorer_client = boto3.client("ce")

# Get Bedrock Model ID from environment variables
MODEL_ID = os.getenv("BEDROCK_MODEL_ID")

def lambda_handler(event, context):
    """
    AWS Lambda function to track LLM usage on AWS Bedrock.
    """
    # Ensure HTTP method key exists
    #http_method = event.get("httpMethod", "test")

    # if http_method == "OPTIONS":
    #     return {
    #         "statusCode": 200,
    #         "headers": {
    #             "Access-Control-Allow-Origin": "*",
    #             "Access-Control-Allow-Methods": "POST, OPTIONS",
    #             "Access-Control-Allow-Headers": "Content-Type"
    #         },
    #         "body": ""
    #     }
    
    try:
        # Parse request payload
        #print(f"event: {event}")
        body = json.loads(event.get("body", "{}"))
        input_text = body.get("input_text", "")

        if not input_text:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "No input text provided"})
            }
     
        # Invoke DeepSeek Model on AWS Bedrock
        response = bedrock_client.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "prompt": f"Human: {input_text} \n\nAssistant:",
                "max_tokens_to_sample": 2000,
                "temperature": 0.7,
                "top_p": 0.9
            })
        )

        cost_data = get_claude_bedrock_cost()
        print(cost_data)

        # Log response
        response_payload = json.loads(response['body'].read().decode('utf-8'))

        return {
            "statusCode": 200,
            # "headers": {
            #     "Access-Control-Allow-Origin": "*",
            #     "Access-Control-Allow-Methods": "POST, OPTIONS",
            #     "Access-Control-Allow-Headers": "Content-Type"
            # },
            "body": json.dumps({
                "message": "lambda handler is sucessfully invoked!",
                "response": response_payload.get("completion", ""),
                "cost": cost_data
            }, indent=2)
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }   

def get_all_aws_services():
    """
    Fetch all AWS services that have reported costs in the last 7 days.
    """
    try:
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=30)  # Fetch last 7 days

        response = cost_explorer_client.get_cost_and_usage(
            TimePeriod={
                "Start": start_date.strftime("%Y-%m-%d"),
                "End": end_date.strftime("%Y-%m-%d"),
            },
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[  
                {"Type": "DIMENSION", "Key": "SERVICE"}
            ]
        )

        print(f"Full response: {json.dumps(response, indent=4)}")  # Debugging

        # Extract all service names
        services = set()
        for entry in response.get("ResultsByTime", []):
            for group in entry.get("Groups", []):
                keys = group.get("Keys", [])
                if keys:
                    services.add(keys[0])  # First key is usually SERVICE

        if services:
            print("Available AWS Services in Cost Explorer:", services)
            return services

        return {"error": "No AWS services with cost data found"}

    except Exception as e:
        print(f"Error fetching AWS services: {str(e)}")
        return {"error": str(e)}

def get_claude_bedrock_cost():
    """
    Fetches the last 3 days' AWS cost for Claude (Amazon Bedrock Edition).
    """
    if not cost_explorer_client:
        return {"error": "AWS Cost Explorer client is not initialized."}

    try:
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=30)  # Fetch last 7 days

        response = cost_explorer_client.get_cost_and_usage(
            TimePeriod={
                "Start": start_date.strftime("%Y-%m-%d"),
                "End": end_date.strftime("%Y-%m-%d"),
            },
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[
                 {"Type": "DIMENSION", "Key": "USAGE_TYPE"}  # Group by USAGE_TYPE to see input/output token counts
             ],
            Filter={
                "Dimensions": {
                    "Key": "SERVICE",
                    "Values": ["Claude (Amazon Bedrock Edition)"]  # Correct Bedrock LLM service name
                }
            }
        )

        print(f"Full response: {json.dumps(response, indent=4)}")  # Debugging

        # Extract cost details
        cost_data = []
        for entry in response.get("ResultsByTime", []):
            for group in entry.get("Groups", []):
                keys = group.get("Keys", [])
                if keys:
                    cost_amount = float(group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", "0.00"))
                    date = entry["TimePeriod"]["Start"]
                    cost_data.append({"date": date, "metric": keys[0], "cost": cost_amount})
            # cost_amount = float(entry.get("Total", {}).get("UnblendedCost", {}).get("Amount", "0.00"))
            # date = entry["TimePeriod"]["Start"]
            # cost_data.append({"date": date, "cost": cost_amount})

        print(cost_data)
        return cost_data

    except Exception as e:
        print(f"Error fetching cost: {str(e)}")
        return {"error": str(e)}


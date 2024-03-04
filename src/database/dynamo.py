import os

class DynamoDB:

    def __init__(self, dynamodb_client):
        self.dynamodb_client = dynamodb_client

    def update(self, display_name, token_info, seed_tracks):
        if not os.environ.get("LOCAL_ENV"):
            self.dynamodb_client.put_item(
                TableName=os.environ.get("USERS_TABLE"),
                Item={
                    "userId": {"S": display_name},
                    "token_info": {"S": str(token_info)},
                    "seed_tracks": {"S": str(seed_tracks)},
                },
            )

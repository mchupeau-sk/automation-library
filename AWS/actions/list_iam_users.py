# coding: utf-8
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from sekoia_automation.action import Action

from aws_helpers.base import AwsModule


class ListIamUsers(Action):
    """List all IAM users in the AWS tenant."""

    module: AwsModule

    def _get_iam_client(self) -> boto3.client:
        """Return a boto3 IAM client, optionally assuming a role via STS."""
        config = self.module.configuration

        if config.aws_role_arn:
            sts_kwargs: dict[str, Any] = {"region_name": config.aws_region_name}
            if config.aws_access_key and config.aws_secret_access_key:
                sts_kwargs["aws_access_key_id"] = config.aws_access_key
                sts_kwargs["aws_secret_access_key"] = config.aws_secret_access_key

            sts_client = boto3.client("sts", **sts_kwargs)
            response = sts_client.assume_role(
                RoleArn=config.aws_role_arn,
                RoleSessionName="sekoia-list-iam-users",
            )
            creds = response["Credentials"]
            session = boto3.Session(
                aws_access_key_id=creds["AccessKeyId"],
                aws_secret_access_key=creds["SecretAccessKey"],
                aws_session_token=creds["SessionToken"],
                region_name=config.aws_region_name,
            )
        else:
            session = boto3.Session(
                aws_access_key_id=config.aws_access_key,
                aws_secret_access_key=config.aws_secret_access_key,
                region_name=config.aws_region_name,
            )

        return session.client("iam")

    def run(self, arguments: dict) -> dict[str, Any]:
        path_prefix = arguments.get("path_prefix", "/")

        try:
            iam = self._get_iam_client()
        except NoCredentialsError as e:
            self.log("AWS credentials not found or invalid", level="error")
            raise
        except (BotoCoreError, ClientError) as e:
            self.log(f"Failed to create IAM client: {e}", level="error")
            raise

        users: list[dict[str, Any]] = []
        paginator = iam.get_paginator("list_users")

        for page in paginator.paginate(PathPrefix=path_prefix):
            for user in page.get("Users", []):
                create_date = user.get("CreateDate")
                password_last_used = user.get("PasswordLastUsed")
                users.append(
                    {
                        "user_id": user.get("UserId"),
                        "user_name": user.get("UserName"),
                        "arn": user.get("Arn"),
                        "path": user.get("Path"),
                        "create_date": create_date.isoformat() if create_date else None,
                        "password_last_used": password_last_used.isoformat() if password_last_used else None,
                    }
                )

        return {"users": users, "count": len(users)}

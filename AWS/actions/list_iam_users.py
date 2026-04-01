# coding: utf-8
from typing import Any

import boto3
from sekoia_automation.action import Action

from aws_helpers.base import AwsModule
from aws_helpers.oidc import OidcAwsMixin


class ListIamUsers(OidcAwsMixin, Action):
    """List all IAM users in the AWS tenant."""

    module: AwsModule

    def _get_iam_client(self) -> boto3.client:
        """Return a boto3 IAM client, using OIDC role assumption when configured."""
        config = self.module.configuration

        if config.aws_role_arn:
            aws_config = self.get_assume_role()
            session = boto3.Session(
                aws_access_key_id=aws_config.aws_access_key_id,
                aws_secret_access_key=aws_config.aws_secret_access_key,
                aws_session_token=aws_config.aws_session_token,
                region_name=aws_config.aws_region,
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

        iam = self._get_iam_client()

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

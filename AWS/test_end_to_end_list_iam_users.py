from pathlib import Path

from aws_helpers.base import AwsModuleConfiguration
from actions.list_iam_users import ListIamUsers

if __name__ == "__main__":
    current_path: Path = Path("/test_data")

    # Option A: authenticate with a static access key / secret
    configuration: AwsModuleConfiguration = AwsModuleConfiguration(
        # aws_access_key="<YOUR_ACCESS_KEY_ID>",
        # aws_secret_access_key="<YOUR_SECRET_ACCESS_KEY>",
        aws_region_name="eu-west-1",
        # Option B: assume a role via STS instead — set aws_role_arn and leave
        # aws_access_key / aws_secret_access_key pointing to a key that has
        # sts:AssumeRole permission on the target role.
        aws_role_arn="arn:aws:iam::123456789012:role/YourRole",
    )

    action = ListIamUsers(data_path=current_path)
    action.module.configuration = configuration

    # Optional: filter users under a specific IAM path prefix.
    # Leave as "/" to list all users.
    arguments = {
        "path_prefix": "/",
    }

    result = action.run(arguments)

    print(f"Total users found: {result['count']}")
    for user in result["users"]:
        print(
            f"  {user['user_name']:40s}  {user['user_id']}  "
            f"created={user['create_date']}  "
            f"last_login={user['password_last_used'] or 'never'}"
        )

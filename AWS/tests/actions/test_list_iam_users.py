# coding: utf-8
from datetime import datetime, timezone
from unittest import mock

import pytest

from actions.list_iam_users import ListIamUsers
from aws_helpers.base import AwsModule, AwsModuleConfiguration


@pytest.fixture
def module_with_keys():
    module = AwsModule()
    module.configuration = AwsModuleConfiguration(
        aws_access_key="fakeAccessKey",
        aws_secret_access_key="fakeSecretKey",
        aws_region_name="eu-west-1",
    )
    return module


@pytest.fixture
def module_with_role():
    module = AwsModule()
    module.configuration = AwsModuleConfiguration(
        aws_access_key="fakeAccessKey",
        aws_secret_access_key="fakeSecretKey",
        aws_region_name="eu-west-1",
        aws_role_arn="arn:aws:iam::123456789012:role/FakeRole",
    )
    return module


def _make_action(module: AwsModule, symphony_storage) -> ListIamUsers:
    action = ListIamUsers(data_path=symphony_storage)
    action.module = module
    action.log = mock.Mock()
    action.log_exception = mock.Mock()
    return action


def _fake_iam_users_pages():
    """Return two pages of users for pagination testing."""
    create_dt = datetime(2023, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    return [
        {
            "Users": [
                {
                    "UserId": "AIDA111111111111AAAAA",
                    "UserName": "alice",
                    "Arn": "arn:aws:iam::123456789012:user/alice",
                    "Path": "/",
                    "CreateDate": create_dt,
                    "PasswordLastUsed": datetime(2024, 6, 1, 8, 0, 0, tzinfo=timezone.utc),
                },
                {
                    "UserId": "AIDA222222222222BBBBB",
                    "UserName": "bob",
                    "Arn": "arn:aws:iam::123456789012:user/bob",
                    "Path": "/",
                    "CreateDate": create_dt,
                },
            ]
        },
        {
            "Users": [
                {
                    "UserId": "AIDA333333333333CCCCC",
                    "UserName": "charlie",
                    "Arn": "arn:aws:iam::123456789012:user/charlie",
                    "Path": "/dev/",
                    "CreateDate": create_dt,
                }
            ]
        },
    ]


def test_list_iam_users_success(module_with_keys, symphony_storage):
    """Happy path: returns all users across paginated responses."""
    action = _make_action(module_with_keys, symphony_storage)

    mock_iam = mock.MagicMock()
    mock_paginator = mock.MagicMock()
    mock_paginator.paginate.return_value = _fake_iam_users_pages()
    mock_iam.get_paginator.return_value = mock_paginator

    mock_session = mock.MagicMock()
    mock_session.client.return_value = mock_iam

    with mock.patch("actions.list_iam_users.boto3.Session", return_value=mock_session):
        result = action.run({})

    assert result["count"] == 3
    assert len(result["users"]) == 3

    alice = next(u for u in result["users"] if u["user_name"] == "alice")
    assert alice["user_id"] == "AIDA111111111111AAAAA"
    assert alice["arn"] == "arn:aws:iam::123456789012:user/alice"
    assert alice["create_date"] == "2023-01-15T10:00:00+00:00"
    assert alice["password_last_used"] == "2024-06-01T08:00:00+00:00"

    bob = next(u for u in result["users"] if u["user_name"] == "bob")
    assert bob["password_last_used"] is None

    mock_paginator.paginate.assert_called_once_with(PathPrefix="/")


def test_list_iam_users_with_path_prefix(module_with_keys, symphony_storage):
    """Passes the path_prefix argument to the IAM paginator."""
    action = _make_action(module_with_keys, symphony_storage)

    mock_iam = mock.MagicMock()
    mock_paginator = mock.MagicMock()
    mock_paginator.paginate.return_value = [{"Users": []}]
    mock_iam.get_paginator.return_value = mock_paginator

    mock_session = mock.MagicMock()
    mock_session.client.return_value = mock_iam

    with mock.patch("actions.list_iam_users.boto3.Session", return_value=mock_session):
        result = action.run({"path_prefix": "/dev/"})

    assert result["count"] == 0
    mock_paginator.paginate.assert_called_once_with(PathPrefix="/dev/")


def test_list_iam_users_empty(module_with_keys, symphony_storage):
    """Returns count=0 when there are no IAM users."""
    action = _make_action(module_with_keys, symphony_storage)

    mock_iam = mock.MagicMock()
    mock_paginator = mock.MagicMock()
    mock_paginator.paginate.return_value = [{"Users": []}]
    mock_iam.get_paginator.return_value = mock_paginator

    mock_session = mock.MagicMock()
    mock_session.client.return_value = mock_iam

    with mock.patch("actions.list_iam_users.boto3.Session", return_value=mock_session):
        result = action.run({})

    assert result == {"users": [], "count": 0}


def test_list_iam_users_role_arn(module_with_role, symphony_storage):
    """When aws_role_arn is set, assumes the role via STS before listing users."""
    action = _make_action(module_with_role, symphony_storage)

    sts_response = {
        "Credentials": {
            "AccessKeyId": "tempAccessKey",
            "SecretAccessKey": "tempSecretKey",
            "SessionToken": "tempToken",
        }
    }
    mock_sts_client = mock.MagicMock()
    mock_sts_client.assume_role.return_value = sts_response

    mock_iam = mock.MagicMock()
    mock_paginator = mock.MagicMock()
    mock_paginator.paginate.return_value = [{"Users": []}]
    mock_iam.get_paginator.return_value = mock_paginator

    mock_role_session = mock.MagicMock()
    mock_role_session.client.return_value = mock_iam

    with mock.patch("actions.list_iam_users.boto3.client", return_value=mock_sts_client) as mock_boto_client, \
         mock.patch("actions.list_iam_users.boto3.Session", return_value=mock_role_session) as mock_boto_session:
        result = action.run({})

    mock_boto_client.assert_called_once_with(
        "sts",
        aws_access_key_id="fakeAccessKey",
        aws_secret_access_key="fakeSecretKey",
        region_name="eu-west-1",
    )
    mock_sts_client.assume_role.assert_called_once_with(
        RoleArn="arn:aws:iam::123456789012:role/FakeRole",
        RoleSessionName="sekoia-list-iam-users",
    )
    mock_boto_session.assert_called_once_with(
        aws_access_key_id="tempAccessKey",
        aws_secret_access_key="tempSecretKey",
        aws_session_token="tempToken",
        region_name="eu-west-1",
    )
    assert result == {"users": [], "count": 0}

#!/usr/bin/env python3
"""
AWS Secrets Manager Rotation Lambda Handler

Implements the 4-step rotation protocol required by AWS Secrets Manager:
1. CREATE  — Generate new credential
2. SET     — Apply to target system
3. TEST    — Validate new credential works
4. FINISH  — Promote new credential to current

This is a reference implementation for PostgreSQL.
For other systems (MySQL, RDS, API keys), adapt the SET and TEST steps.

Security Notes:
- Username is safely quoted using psycopg2.sql.Identifier
- Secrets Manager state is authoritative; Lambda failures trigger retry
- Credentials are stored as JSON in Secrets Manager
- Uses AWS-native password generation
"""

import json
import boto3
import psycopg2
from psycopg2 import sql
import os
import logging

# Initialize clients
secrets_client = boto3.client('secretsmanager')

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_secret_dict(secret_id, stage, token=None):
    """
    Retrieve secret value from Secrets Manager.
    """
    try:
        if stage == "AWSPENDING":
            response = secrets_client.get_secret_value(
                SecretId=secret_id,
                VersionId=token,
                VersionStage=stage
            )
        else:
            response = secrets_client.get_secret_value(
                SecretId=secret_id,
                VersionStage=stage
            )

        return json.loads(response['SecretString'])

    except Exception as e:
        logger.error(f"Error retrieving secret stage {stage}: {str(e)}")
        raise


def validate_pending_version(secret_id, token):
    """
    Validate that the rotation token exists and is marked AWSPENDING.
    """

    metadata = secrets_client.describe_secret(
        SecretId=secret_id
    )

    versions = metadata.get("VersionIdsToStages", {})

    if token not in versions:
        raise ValueError(f"Rotation token {token} not found")

    if "AWSPENDING" not in versions[token]:
        raise ValueError(f"Version {token} is not marked AWSPENDING")


def set_secret_version_stage(secret_id, version_id, stage):
    """
    Move version to a new stage.
    """

    try:
        metadata = secrets_client.describe_secret(
            SecretId=secret_id
        )

        current_version = None

        for existing_version, stages in metadata["VersionIdsToStages"].items():
            if "AWSCURRENT" in stages:
                current_version = existing_version
                break

        secrets_client.update_secret_version_stage(
            SecretId=secret_id,
            VersionStage=stage,
            MoveToVersionId=version_id,
            RemoveFromVersionId=current_version
        )

        logger.info(f"Moved version {version_id} to stage {stage}")

    except Exception as e:
        logger.error(f"Error updating version stage: {str(e)}")
        raise


def connect_to_database(host, port, user, password, database):
    """
    Establish PostgreSQL connection.
    """

    try:
        return psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            sslmode="require",
            connect_timeout=10
        )

    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        raise


def create_secret(secret_id, client_request_token):
    """
    CREATE step:
    Generate new password and store as AWSPENDING.
    """

    logger.info("CREATE: Generating new password")

    # Validate if version already exists
    metadata = secrets_client.describe_secret(
        SecretId=secret_id
    )

    versions = metadata.get("VersionIdsToStages", {})

    if client_request_token in versions:
        if "AWSPENDING" in versions[client_request_token]:
            logger.info("CREATE: Version already exists")
            return

    current_secret = get_secret_dict(
        secret_id,
        "AWSCURRENT"
    )

    username = current_secret['username']

    # AWS-native secure password generation
    new_password = secrets_client.get_random_password(
        PasswordLength=32,
        ExcludeCharacters='/@"\\'
    )['RandomPassword']

    new_secret = {
        'username': username,
        'password': new_password
    }

    try:
        secrets_client.put_secret_value(
            SecretId=secret_id,
            ClientRequestToken=client_request_token,
            SecretString=json.dumps(new_secret),
            VersionStages=['AWSPENDING']
        )

        logger.info("CREATE: New AWSPENDING version created")

    except Exception as e:
        logger.error(f"CREATE failed: {str(e)}")
        raise


def set_secret(secret_id, client_request_token):
    """
    SET step:
    Apply new password to PostgreSQL user.
    """

    logger.info("SET: Applying new password")

    validate_pending_version(secret_id, client_request_token)

    current_secret = get_secret_dict(
        secret_id,
        "AWSCURRENT"
    )

    pending_secret = get_secret_dict(
        secret_id,
        "AWSPENDING",
        client_request_token
    )

    username = current_secret['username']
    current_password = current_secret['password']
    new_password = pending_secret['password']

    host = os.environ.get('DB_HOST', 'localhost')
    port = os.environ.get('DB_PORT', '5432')
    database = os.environ.get('DB_NAME', 'postgres')

    try:
        # Use context managers for automatic cleanup
        with connect_to_database(
            host,
            port,
            username,
            current_password,
            database
        ) as conn:

            with conn.cursor() as cur:

                # Safely quote username identifier
                cur.execute(
                    sql.SQL(
                        "ALTER USER {} WITH PASSWORD %s"
                    ).format(
                        sql.Identifier(username)
                    ),
                    (new_password,)
                )

                conn.commit()

        logger.info(f"SET: Password updated for user {username}")

    except Exception as e:
        logger.error(f"SET failed: {str(e)}")
        raise


def test_secret(secret_id, client_request_token):
    """
    TEST step:
    Validate new credentials work.
    """

    logger.info("TEST: Validating new credentials")

    validate_pending_version(secret_id, client_request_token)

    pending_secret = get_secret_dict(
        secret_id,
        "AWSPENDING",
        client_request_token
    )

    username = pending_secret['username']
    new_password = pending_secret['password']

    host = os.environ.get('DB_HOST', 'localhost')
    port = os.environ.get('DB_PORT', '5432')
    database = os.environ.get('DB_NAME', 'postgres')

    try:
        with connect_to_database(
            host,
            port,
            username,
            new_password,
            database
        ) as conn:

            with conn.cursor() as cur:

                cur.execute("SELECT version();")
                result = cur.fetchone()

        logger.info(
            f"TEST: Successfully connected. "
            f"Version: {result[0][:50]}"
        )

    except Exception as e:
        logger.error(f"TEST failed: {str(e)}")
        raise


def finish_secret(secret_id, client_request_token):
    """
    FINISH step:
    Promote AWSPENDING -> AWSCURRENT.
    """

    logger.info("FINISH: Promoting new version")

    validate_pending_version(secret_id, client_request_token)

    try:
        set_secret_version_stage(
            secret_id,
            client_request_token,
            "AWSCURRENT"
        )

        logger.info("FINISH: Rotation completed")

    except Exception as e:
        logger.error(f"FINISH failed: {str(e)}")
        raise


def lambda_handler(event, context):
    """
    Main Lambda handler.

    AWS Secrets Manager invokes this with:
    {
        "SecretId": "arn:aws:secretsmanager:...",
        "Step": "create|set|test|finish",
        "Token": "version-token-uuid"
    }
    """

    secret_id = event['SecretId']
    step = event['Step']
    token = event.get('Token', '')

    logger.info(f"Rotation Lambda invoked: step={step}")

    try:

        if step == "create":
            create_secret(secret_id, token)

        elif step == "set":
            set_secret(secret_id, token)

        elif step == "test":
            test_secret(secret_id, token)

        elif step == "finish":
            finish_secret(secret_id, token)

        else:
            raise ValueError(
                f"Invalid step: {step}. "
                f"Must be create|set|test|finish"
            )

        logger.info(f"Step '{step}' completed successfully")

        return {
            'statusCode': 200,
            'body': json.dumps(
                f"Rotation step '{step}' completed successfully"
            )
        }

    except Exception as e:

        logger.error(
            f"Rotation failed at step '{step}': {str(e)}"
        )

        # AWS Secrets Manager automatically retries failures
        raise


# TODO (Production Hardening):
# - Add CloudWatch metrics
# - Add SNS notifications
# - Add exponential retry handling
# - Add support for MySQL/Oracle
# - Add certificate pinning
# - Add VPC endpoint support
# - Add audit logging
# - Add structured JSON logging

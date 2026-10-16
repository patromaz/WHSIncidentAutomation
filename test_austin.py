import json

import os

import sqlite3

from datetime import datetime, timedelta, timezone

from pathlib import Path

from zoneinfo import ZoneInfo

import requests

from dotenv import load_dotenv

# ============================================================

# CONFIGURATION

# ============================================================

load_dotenv()

AUSTIN_ACCESS_TOKEN = os.getenv("AUSTIN_ACCESS_TOKEN")

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

GRAPHQL_URL = (

    "https://wqkmwaqtpfhs3iiylaqxmju7fy."

    "appsync-api.us-east-1.amazonaws.com/graphql"

)

DATABASE_FILE = Path("incidents.db")

# How far back to search each time the bot runs.

# We will eventually run the bot every 30 minutes.

LOOKBACK_HOURS = 24

# ============================================================

# GRAPHQL QUERY

# ============================================================

QUERY = """

query searchIncidentsV2(

    $filter: AWSJSON!,

    $pageInfo: PageInfoInput!,

    $sortInfos: [SortInfoInput!]

) {

    searchIncidentsV2(

        input: {

            pageInfo: $pageInfo,

            sortInfos: $sortInfos,

            filter: $filter

        }

    ) {

        count

        entities {

            injuredPersonData {

                alias

                managerAlias

                shiftPattern

            }

            createdAt

            updatedAt

            id

            incidentDateTime

            incidentReportedDateTime

            caseNumber

            incidentGroupId

            customSearchAttributes {

                key

                value

            }

            status

            type

        }

        pageInfo {

            from

        }

    }

}

"""

# ============================================================

# BASE INCIDENT FILTER

# ============================================================

BASE_FILTER = {

    "composeOperator": "AND",

    "queryFilters": [

        {

            "filterType": "MUST",

            "queryParams": [

                {

                    "field": "type",

                    "queryType": "MATCH",

                    "value": ["INJURY"]

                }

            ]

        },

        {

            "filterType": "MUST",

            "queryParams": [

                {

                    "field": "customSearchAttributes.key",

                    "queryType": "MATCH",

                    "value": ["latestMedicalStatus"]

                },

                {

                    "field": "customSearchAttributes.value",

                    "queryType": "MATCH",

                    "value": [

                        "claim-filed",

                        "closed",

                        "open",

                        "suspended",

                        "pending-outside-medical"

                    ]

                }

            ]

        },

        {

            "filterType": "MUST",

            "queryParams": [

                {

                    "field": "dynamicScope.nodeIds.id",

                    "queryType": "MATCH",

                    "value": [

                        "TDA|176a3f65-c16e-4eb4-8295-4a0152d32464"

                    ]

                }

            ]

        }

    ],

    "subCompositions": [

        {

            "composeOperator": "OR",

            "queryFilters": [

                {

                    "filterType": "MUST",

                    "queryParams": [

                        {

                            "field": "customSearchAttributes.key",

                            "queryType": "MATCH",

                            "value": ["EXTERNAL_SERVICE"]

                        },

                        {

                            "field": "customSearchAttributes.value",

                            "queryType": "MATCH",

                            "value": ["EMT"]

                        }

                    ]

                },

                {

                    "filterType": "MUST_NOT",

                    "queryParams": [

                        {

                            "field": "customSearchAttributes.key",

                            "queryType": "MATCH",

                            "value": ["EXTERNAL_SERVICE"]

                        }

                    ]

                }

            ]

        }

    ]

}

# ============================================================

# BUILD DATE FILTER

# ============================================================

def build_filter():

    """

    Create a fresh filter for every run.

    We search the previous LOOKBACK_HOURS hours based on

    when the incident record was CREATED in Austin.

    Example:

        Current time: 12:00

        Lookback: 2 hours

        createdAt >= 10:00

        createdAt <= 12:00

    """

    now_utc = datetime.now(timezone.utc)

    lookback_time = (

        now_utc - timedelta(hours=LOOKBACK_HOURS)

    )

    created_after = (

        lookback_time

        .isoformat(timespec="milliseconds")

        .replace("+00:00", "Z")

    )

    created_before = (

        now_utc

        .isoformat(timespec="milliseconds")

        .replace("+00:00", "Z")

    )

    incident_filter = json.loads(

        json.dumps(BASE_FILTER)

    )

    incident_filter["queryFilters"].append(

        {

            "filterType": "MUST",

            "queryParams": [

                {

                    "field": "createdAt",

                    "queryType": "GREATER_THAN_EQUAL",

                    "value": [created_after]

                }

            ]

        }

    )

    incident_filter["queryFilters"].append(

        {

            "filterType": "MUST",

            "queryParams": [

                {

                    "field": "createdAt",

                    "queryType": "LESS_THAN_EQUAL",

                    "value": [created_before]

                }

            ]

        }

    )

    print(

        f"Searching Austin from "

        f"{created_after} to {created_before}"

    )

    return incident_filter

# ============================================================

# GRAPHQL VARIABLES

# ============================================================

def build_variables():

    incident_filter = build_filter()

    return {

        "filter": json.dumps(incident_filter),

        "pageInfo": {

            "from": 0,

            "size": 25

        },

        "sortInfos": [

            {

                "direction": "DESC",

                "field": "createdAt"

            },

            {

                "direction": "DESC",

                "field": "updatedAt"

            }

        ]

    }

# ============================================================

# HTTP HEADERS

# ============================================================

def build_headers():

    return {

        "Content-Type": "application/json",

        "Accept": "application/json",

        "Authorization": AUSTIN_ACCESS_TOKEN or ""

    }

# ============================================================

# DATABASE FUNCTIONS

# ============================================================

def setup_database():

    connection = sqlite3.connect(

        DATABASE_FILE

    )

    cursor = connection.cursor()

    cursor.execute(

        """

        CREATE TABLE IF NOT EXISTS incidents (

            case_number TEXT PRIMARY KEY,

            first_seen TEXT NOT NULL

        )

        """

    )

    connection.commit()

    connection.close()

def database_is_empty():

    connection = sqlite3.connect(

        DATABASE_FILE

    )

    cursor = connection.cursor()

    cursor.execute(

        "SELECT COUNT(*) FROM incidents"

    )

    count = cursor.fetchone()[0]

    connection.close()

    return count == 0

def case_already_seen(case_number):

    connection = sqlite3.connect(

        DATABASE_FILE

    )

    cursor = connection.cursor()

    cursor.execute(

        """

        SELECT 1

        FROM incidents

        WHERE case_number = ?

        """,

        (case_number,)

    )

    result = cursor.fetchone()

    connection.close()

    return result is not None

def save_case(case_number):

    connection = sqlite3.connect(

        DATABASE_FILE

    )

    cursor = connection.cursor()

    cursor.execute(

        """

        INSERT OR IGNORE INTO incidents

        (case_number, first_seen)

        VALUES (?, ?)

        """,

        (

            case_number,

            datetime.now().isoformat()

        )

    )

    connection.commit()

    connection.close()

# ============================================================

# CUSTOM ATTRIBUTE HELPER

# ============================================================

def get_custom_attribute(attributes, key):

    if not attributes:

        return None

    for attribute in attributes:

        if attribute.get("key") == key:

            return attribute.get("value")

    return None

# ============================================================

# TIME CONVERSION

# ============================================================

def convert_to_central(timestamp):

    if not timestamp:

        return "Unknown"

    try:

        utc_time = datetime.fromisoformat(

            timestamp.replace("Z", "+00:00")

        )

        central_time = utc_time.astimezone(

            ZoneInfo("America/Chicago")

        )

        return central_time.strftime(

            "%m/%d/%Y %I:%M %p CT"

        )

    except Exception as error:

        print(

            f"WARNING: Could not convert timestamp "

            f"{timestamp}: {error}"

        )

        return timestamp

# ============================================================

# SLACK FUNCTION

# ============================================================

def send_slack_message(message):

    if not SLACK_WEBHOOK_URL:

        print(

            "ERROR: Slack webhook URL is not configured."

        )

        return False

    try:

        # DEBUG: inspect the outgoing message without printing its contents.
        print(
            "DEBUG: Message contains webhook identifier:",
            "E015GUGD2V6" in message
        )
        print("DEBUG: Outgoing message length:", len(message))
        print(
            "DEBUG: Identifier positions:",
            [
                i for i in range(len(message))
                if message.startswith("E015GUGD2V6", i)
            ]
        )

        response = requests.post(

            SLACK_WEBHOOK_URL,

            json={

                "text": message

            },

            timeout=15

        )

    except requests.RequestException as error:

        print(

            "ERROR: Could not connect to Slack."

        )

        print(error)

        return False

    if response.status_code == 200:

        print(

            "Slack message sent successfully."

        )

        return True

    print(

        f"ERROR: Slack returned HTTP "

        f"{response.status_code}"

    )

    print(response.text)

    return False

# ============================================================

# SLACK MESSAGE BUILDER

# ============================================================

def build_slack_message(incident):

    case_number = incident.get(

        "caseNumber",

        "Unknown"

    )

    incident_date_time = convert_to_central(

        incident.get("incidentDateTime")

    )

    injured_person_data = (

        incident.get("injuredPersonData")

        or {}

    )

    aa_login = (

        injured_person_data.get("alias")

        or "Unknown"

    )

    shift_code = (

        injured_person_data.get("shiftPattern")

        or "Unknown"

    )

    attributes = (

        incident.get("customSearchAttributes")

        or []

    )

    process_path = (

        get_custom_attribute(

            attributes,

            "processPathName"

        )

        or "Unknown"

    )

    area_injury = (

        get_custom_attribute(

            attributes,

            "incidentLocation"

        )

        or "Unknown"

    )

    case_notes = (

        get_custom_attribute(

            attributes,

            "incidentDescription"

        )

        or "No case notes available."

    )

    incident_group_id = (

        incident.get("incidentGroupId")

        or ""

    )

    case_url = (

        "https://na.ehs-amazon.com/incidents/group/"

        f"{incident_group_id}/incident/"

        f"{case_number}/summary"

    )

    message = (

        "🚨 *At Risk Incident*\n\n"

        "*Type of Escalation:* At Risk\n"

        f"*Incident Date and Time:* "

        f"{incident_date_time}\n"

        f"*AA Login:* "

        f"{aa_login}\n"

        f"*Shift Code:* "

        f"{shift_code}\n"

        f"*Process Path:* "

        f"{process_path}\n"

        f"*Area Injury Occurred:* "

        f"{area_injury}\n"

        f"*Austin Case:* "

        f"<{case_url}|{case_number}>\n"

        f"*Case Notes:* "

        f"{case_notes}"

    )

    return message

# ============================================================

# MAIN PROGRAM

# ============================================================

def main():

    print()

    print("==========================================")

    print("       AUSTIN SLACK INCIDENT BOT")

    print("==========================================")

    print()

    # --------------------------------------------------------

    # Check Austin token

    # --------------------------------------------------------

    if not AUSTIN_ACCESS_TOKEN:

        print(

            "ERROR: AUSTIN_ACCESS_TOKEN was not found."

        )

        print(

            "Check your .env file."

        )

        return

    print(

        "Austin authorization token loaded."

    )

    # --------------------------------------------------------

    # Check Slack webhook

    # --------------------------------------------------------

    if not SLACK_WEBHOOK_URL:

        print(

            "ERROR: SLACK_WEBHOOK_URL was not found."

        )

        print(

            "Check your .env file."

        )

        return

    print(

        "Slack webhook loaded successfully."

    )

    # --------------------------------------------------------

    # Set up database

    # --------------------------------------------------------

    setup_database()

    if database_is_empty():

        print(

            "Database is empty."

        )

        print(

            "Creating baseline from existing "

            "recent incidents..."

        )

        baseline_mode = True

    else:

        print(

            "Existing case database found."

        )

        baseline_mode = False

    # --------------------------------------------------------

    # Build fresh API request

    # --------------------------------------------------------

    variables = build_variables()

    headers = build_headers()

    payload = {

        "query": QUERY,

        "variables": variables

    }

    # --------------------------------------------------------

    # Connect to Austin

    # --------------------------------------------------------

    print(

        "Connecting to Austin..."

    )

    try:

        response = requests.post(

            GRAPHQL_URL,

            headers=headers,

            json=payload,

            timeout=30

        )

    except requests.RequestException as error:

        print(

            "ERROR: Could not connect to Austin."

        )

        print(error)

        return

    print(

        f"HTTP status: {response.status_code}"

    )

    # --------------------------------------------------------

    # Check HTTP response

    # --------------------------------------------------------

    if response.status_code != 200:

        print(

            "ERROR: Austin returned a "

            "non-200 response."

        )

        print(response.text)

        return

    # --------------------------------------------------------

    # Parse JSON

    # --------------------------------------------------------

    try:

        data = response.json()

    except ValueError:

        print(

            "ERROR: Austin response was "

            "not valid JSON."

        )

        print(response.text)

        return

    # --------------------------------------------------------

    # Check GraphQL errors

    # --------------------------------------------------------

    if "errors" in data:

        print(

            "ERROR: Austin GraphQL returned errors."

        )

        print(

            json.dumps(

                data["errors"],

                indent=2

            )

        )

        return

    # --------------------------------------------------------

    # Extract incidents

    # --------------------------------------------------------

    search_results = (

        data

        .get("data", {})

        .get("searchIncidentsV2", {})

    )

    incidents = search_results.get(

        "entities",

        []

    )

    print()

    print(

        f"Successfully retrieved "

        f"{len(incidents)} incidents."

    )

    print()

    # --------------------------------------------------------

    # First-run baseline

    # --------------------------------------------------------

    if baseline_mode:

        print(

            "=========================================="

        )

        print(

            "BASELINE MODE"

        )

        print(

            "Existing recent incidents will be saved "

            "without sending Slack notifications."

        )

        print(

            "=========================================="

        )

        print()

        for incident in incidents:

            case_number = incident.get(

                "caseNumber"

            )

            if not case_number:

                continue

            if not case_already_seen(

                case_number

            ):

                save_case(

                    case_number

                )

                print(

                    f"BASELINE: {case_number}"

                )

        print()

        print(

            "Baseline complete."

        )

        print(

            "No Slack notifications were sent."

        )

        return

    # --------------------------------------------------------

    # Process incidents

    # --------------------------------------------------------

    for incident in incidents:

        case_number = incident.get(

            "caseNumber"

        )

        # --------------------------------------------

        # Skip missing case numbers

        # --------------------------------------------

        if not case_number:

            print(

                "WARNING: Incident without "

                "case number skipped."

            )

            continue

        # --------------------------------------------

        # Existing case

        # --------------------------------------------

        if case_already_seen(

            case_number

        ):

            print(

                f"ALREADY SEEN: {case_number}"

            )

            continue

        # --------------------------------------------

        # New case

        # --------------------------------------------

        print(

            f"NEW CASE: {case_number}"

        )

        # --------------------------------------------

        # Build Slack message

        # --------------------------------------------

        message = build_slack_message(

            incident

        )

        print("DEBUG: Message length:", len(message))
        print(
            "DEBUG: Message starts correctly:",
            message.startswith("🚨 *At Risk Incident*")
        )

        print()

        print(

            "Sending Slack notification..."

        )

        # --------------------------------------------

        # Send Slack notification

        # --------------------------------------------

        slack_success = send_slack_message(

            message

        )

        # --------------------------------------------

        # Save ONLY after Slack succeeds

        # --------------------------------------------

        if slack_success:

            save_case(

                case_number

            )

            print(

                f"SAVED: {case_number}"

            )

        else:

            print(

                f"NOT SAVED: {case_number}"

            )

            print(

                "Slack notification failed. "

                "The case will be retried on "

                "the next run."

            )

        print()

    print(

        "=========================================="

    )

    print(

        "Run complete."

    )

    print(

        "=========================================="

    )

# ============================================================

# PROGRAM ENTRY POINT

# ============================================================

if __name__ == "__main__":

    main()

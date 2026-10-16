# Austin Incident to Slack Notification Bot

A Python automation tool that checks the Austin incident management system for new injury incidents and sends notifications to a designated Slack channel through a Slack Workflow webhook.

The bot uses GraphQL to retrieve incident data, SQLite to track previously processed cases, and Slack Workflow Builder to deliver notifications.

## Features

- Polls the Austin incident system for recently created incidents.
- Retrieves incident information through a GraphQL API.
- Filters incidents according to configured criteria.
- Prevents duplicate notifications using a SQLite database.
- Formats incident information into a Slack message.
- Sends notifications through a Slack Workflow webhook.
- Supports scheduled execution through Windows Task Scheduler.

## How It Works

1. The bot connects to the Austin GraphQL API using an authorization token.
2. It retrieves incidents created within the configured lookback period.
3. It checks each incident's case number against the local SQLite database.
4. New incidents are formatted into a Slack notification.
5. The notification is sent to the configured Slack Workflow webhook.
6. After a successful Slack response, the case number is recorded in the database.
7. Previously processed incidents are skipped during subsequent runs.

## Technologies Used

- Python
- GraphQL
- SQLite
- Requests
- Slack Workflow Builder
- Windows Task Scheduler

## Prerequisites

Before running the bot, you will need:

- Python installed on your machine.
- Access to the Austin incident management API.
- A valid Austin API authorization token.
- A configured Slack Workflow webhook.
- Permission to send messages through the designated Slack workflow.

## Installation

Clone the repository:

```bash
git clone <repository-url>
cd austin-slack-bot-2
```

Create a Python virtual environment:

```bash
python -m venv .venv
```

Activate the environment on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project directory.

Configure the following environment variables:

```dotenv
AUSTIN_ACCESS_TOKEN=your_austin_access_token
SLACK_WEBHOOK_URL=your_slack_workflow_webhook
```

Do not commit the `.env` file or expose API tokens and webhook URLs in source code, logs, screenshots, or GitHub issues.

## Running the Bot

Run the script manually:

```bash
python test_austin.py
```

The bot should report its connection status, number of incidents retrieved, and whether cases were skipped, successfully notified, or saved to the database.

## Database and Duplicate Prevention

The bot uses `incidents.db` to track previously processed incidents.

Each case number is stored as a unique record. This prevents the same incident from generating repeated Slack notifications during future polling runs.

A case is recorded after the Slack notification succeeds. If notification delivery fails, the case is not marked as successfully processed and can be retried on a subsequent run.

Do not delete or reset the production database simply to test the notification workflow.

## Slack Workflow Setup

The Slack Workflow Builder workflow should:

1. Use a webhook trigger.
2. Accept the incoming notification text.
3. Pass that text into the Slack message step.
4. Post the message to the designated channel.

The Slack webhook URL must be configured in the `.env` file.

## Scheduling

The bot can be scheduled through Windows Task Scheduler.

The current configuration runs the bot every 30 minutes. Each execution checks the configured lookback period and relies on the SQLite database to avoid duplicate notifications.

## Testing

The Slack notification can be tested independently from the Austin API and production incident database.

Use the standalone Slack test script:

```bash
python test_slack_message.py
```

This verifies that the configured Slack webhook can receive a test message without requiring a new incident to appear.

Do not use real incident information in test messages unless authorized.

## Troubleshooting

| Issue | Possible cause |
|---|---|
| HTTP 401 from Austin | Authorization token is missing, invalid, or expired |
| Missing environment variable | `.env` file is not being loaded or the variable name is incorrect |
| Slack workflow returns `workflow_not_published` | The Slack workflow has not been published |
| Slack notification is not delivered | Webhook configuration or Slack workflow trigger may be incorrect |
| Timezone error | Required timezone data may be missing from the Python environment |
| Existing case is skipped | The case number is already recorded in the SQLite database |

## Security and Privacy

This project interacts with an internal incident management system and may process sensitive workplace or medical information.

- Keep API tokens and webhook URLs private.
- Never commit `.env` files, database files containing real incident data, or sensitive logs.
- Use synthetic incident data for demonstrations and testing.
- Follow applicable organizational policies before sharing or publishing this project.

## Future Improvements

Potential improvements include:

- More robust handling of expired API tokens.
- Configurable polling intervals and lookback periods.
- Improved logging and error reporting.
- Automated tests for incident filtering and message formatting.
- Better monitoring of failed notification attempts.

## License

Add the license applicable to this project here.

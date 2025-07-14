**ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [SMTP](./README.md)

# SMTP Adapter

The SMTP adapter provides a standardized interface for email delivery in ACB applications, supporting both direct SMTP connections and email service APIs.

## Overview

The ACB SMTP adapter offers:

- Consistent email sending interface
- Support for multiple email delivery methods
- Template-based email rendering
- Attachment handling
- HTML and plain text emails
- Email forwarding configuration

## Available Implementations

| Implementation | Description | Best For |
|----------------|-------------|----------|
| **Gmail** | Send emails through Gmail API with OAuth2 | Google Workspace users, personal Gmail accounts |
| **Mailgun** | Send emails through Mailgun API | High-volume email delivery, transactional emails |

## Installation

```bash
# Install with SMTP support
uv add "acb[smtp]"

# Or with specific implementation
uv add "acb[gmail]"
uv add "acb[mailgun]"

# Or include it with other dependencies
uv add "acb[smtp,templates]"
```

## Configuration

### Settings

Configure the SMTP adapter in your `settings/adapters.yml` file:

```yaml
# Use Gmail implementation
smtp: gmail

# Or use Mailgun implementation
smtp: mailgun

# Or disable email functionality
smtp: null
```

### SMTP Settings

The SMTP adapter settings can be customized in your `settings/app.yml` file:

```yaml
smtp:
  # Required adapters (will ensure these are loaded first)
  requires: ["requests"]

  # Common settings
  domain: "mail.example.com"  # Defaults to mail.{your app domain}
  default_from: "info@example.com"  # Defaults to info@{your app domain}
  default_from_name: "My Application"  # Defaults to your app title
  test_receiver: "test@example.com"
  template_folder: "./templates/email"

  # Email forwarding configuration
  forwards:
    admin: "admin@example.com"
    info: "info@example.com"
    support: "support@example.com"

  # Mailgun specific settings
  api_key: "your-mailgun-api-key"
  api_url: "https://api.mailgun.net/v3/domains"

  # Gmail specific settings
  client_id: "your-google-client-id"
  client_secret: "your-google-client-secret"
  refresh_token: "your-google-refresh-token"
  scopes: [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.settings.basic",
    "https://www.googleapis.com/auth/gmail.settings.sharing"
  ]

  # SMTP server configuration (for direct SMTP connections)
  port: 587
  tls: true
  ssl: false
```

## Basic Usage

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the SMTP adapter
SMTP = import_adapter("smtp")

# Get the SMTP instance via dependency injection
smtp = depends.get(SMTP)

# Send a simple email
await smtp.send_email(
    to="recipient@example.com",
    subject="Hello from ACB",
    body="This is a test email sent from the ACB framework."
)

# Send an HTML email
html_content = """
<html>
<body>
    <h1>Hello from ACB</h1>
    <p>This is a <strong>formatted</strong> email with <em>HTML</em> content.</p>
</body>
</html>
"""

await smtp.send_email(
    to="recipient@example.com",
    subject="HTML Email Test",
    body=html_content,
    html=True
)
```

## Advanced Usage

### Gmail Setup

To use the Gmail adapter, you need to set up OAuth2 credentials:

1. Create a Google Cloud project at [console.cloud.google.com](https://console.cloud.google.com/)
2. Enable the Gmail API for your project
3. Create OAuth2 credentials (client ID and client secret)
4. Generate a refresh token using the OAuth2 flow
5. Configure your ACB application with these credentials

```yaml
smtp:
  client_id: "your-google-client-id"
  client_secret: "your-google-client-secret"
  refresh_token: "your-google-refresh-token"
```

The Gmail adapter uses these credentials to authenticate with the Gmail API and send emails on behalf of the authenticated user. It also supports email forwarding configuration through Gmail's forwarding settings.

### Sending to Multiple Recipients

```python
from acb.depends import depends
from acb.adapters import import_adapter

SMTP = import_adapter("smtp")
smtp = depends.get(SMTP)

# Send to multiple recipients
await smtp.send_email(
    to=["user1@example.com", "user2@example.com", "user3@example.com"],
    subject="Team Update",
    body="This is a message for the entire team."
)

# Using CC and BCC
await smtp.send_email(
    to="primary@example.com",
    cc=["manager1@example.com", "manager2@example.com"],
    bcc=["archive@example.com"],
    subject="Project Status Update",
    body="Here's the latest project status report."
)
```

### Sending with Attachments

```python
from anyio import Path as AsyncPath

# Send an email with attachments
await smtp.send_email(
    to="recipient@example.com",
    subject="Report Attached",
    body="Please find the monthly report attached.",
    attachments=[
        {
            "filename": "report.pdf",
            "path": AsyncPath("./reports/monthly_report.pdf"),
            "mime_type": "application/pdf"
        },
        {
            "filename": "data.xlsx",
            "path": AsyncPath("./reports/data.xlsx"),
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        }
    ]
)
```

### Using Templates

```python
# Send an email using a template
await smtp.send_template(
    to="customer@example.com",
    subject="Order Confirmation",
    template_name="order_confirmation.html",
    template_data={
        "customer_name": "John Doe",
        "order_id": "ORD-12345",
        "order_date": "2023-05-15",
        "items": [
            {"name": "Product A", "quantity": 2, "price": 29.99},
            {"name": "Product B", "quantity": 1, "price": 49.99}
        ],
        "total": 109.97
    }
)
```

### Custom From Address

```python
# Send from a specific address
await smtp.send_email(
    to="recipient@example.com",
    subject="Sales Inquiry",
    body="Thank you for your sales inquiry...",
    from_email="sales@example.com",
    from_name="Sales Department"
)
```

### Email Forwarding

```python
# Forward an incoming email
original_email = {
    "from": "customer@external.com",
    "subject": "Help needed",
    "body": "I'm having trouble with my account...",
    "received_at": "2023-05-16T14:32:45Z"
}

await smtp.forward_email(
    email=original_email,
    to="support@example.com",
    prefix="[CUSTOMER INQUIRY]"
)
```

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - **Problem**: `SMTPAuthenticationError: Authentication failed`
   - **Solution**: Check your email credentials and ensure they're correctly configured

2. **Connection Issues**
   - **Problem**: `SMTPConnectError: Failed to connect to SMTP server`
   - **Solution**: Verify the SMTP server address and port; check if TLS/SSL settings are correct

3. **Rate Limiting**
   - **Problem**: `SMTPRateLimitError: Too many emails sent`
   - **Solution**: Implement throttling or use a service with higher sending limits

4. **Email Delivery Failures**
   - **Problem**: Emails not being delivered
   - **Solution**: Check spam filters, verify recipient addresses, and ensure sender domain has proper SPF/DKIM setup

## Implementation Details

The SMTP adapter implements these core methods:

```python
class EmailBase:
    async def send_email(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
        html: bool = False,
        attachments: Optional[list[dict]] = None
    ) -> bool: ...

    async def send_template(
        self,
        to: str | list[str],
        subject: str,
        template_name: str,
        template_data: dict,
        **kwargs
    ) -> bool: ...

    async def forward_email(
        self,
        email: dict,
        to: str | list[str],
        prefix: Optional[str] = None
    ) -> bool: ...
```

## Additional Resources

- [Gmail API Documentation](https://developers.google.com/gmail/api/guides)
- [Gmail OAuth2 Setup Guide](https://developers.google.com/gmail/api/auth/about-auth)
- [Mailgun API Documentation](https://documentation.mailgun.com/)
- [Email Templates Best Practices](https://www.litmus.com/blog/email-coding-best-practices/)
- [ACB Templates Documentation](../../README.md#templates)

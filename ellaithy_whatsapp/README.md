# Ellaithy WhatsApp for Odoo 18 Community

Technical name: `ellaithy_whatsapp`

## Features
- Meta WhatsApp Business Platform / Cloud API connection.
- Multi-number / multi-account configuration.
- Public webhook endpoint: `/ellaithy_whatsapp/webhook`.
- HMAC signature verification when App Secret is configured.
- Incoming text, image, document, audio, video, location and interactive replies.
- Outgoing text, approved Meta templates, image/document/audio/video attachments.
- Sent / delivered / read / failed status tracking.
- Inbox with assignment, team, unread count, state and response metrics.
- Round-robin agent assignment.
- Optional contact and CRM lead auto-creation for unknown numbers.
- CRM, Complaint and Helpdesk buttons and message logging in chatter.
- Native graph/pivot reporting.
- Roles: WhatsApp User, Supervisor, Administrator.

## Meta setup
1. Create or use a Meta Business app with WhatsApp Business Platform.
2. Add a phone number and obtain the Phone Number ID and permanent/system-user access token.
3. In Odoo open WhatsApp > Configuration > Accounts.
4. Enter Phone Number ID, access token, Verify Token and App Secret.
5. Copy the Odoo Webhook URL shown on the account.
6. Configure the same URL and Verify Token in Meta Webhooks.
7. Subscribe to WhatsApp `messages` webhook events.
8. Test connection from the Odoo account form.

## Important
- This module does not use Odoo Enterprise WhatsApp.
- It calls Meta's Graph API directly.
- The Graph API version is configurable per account.
- Meta template approval is done in Meta Business Manager / WhatsApp Manager; Odoo stores the approved template name/language for sending.
- The server must be publicly reachable over HTTPS for Meta webhook delivery.

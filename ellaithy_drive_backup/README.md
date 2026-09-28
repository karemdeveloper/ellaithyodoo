# Ellaithy Google Drive Backup - Odoo 18 Community

## Features
- Manual **Backup Now** button.
- Automatic daily backups.
- ZIP backup including database + Odoo filestore.
- PostgreSQL custom dump option for database-only backups.
- Google Drive resumable upload through REST API.
- No Google Python SDK required.
- Configurable retention and cleanup of old Drive backups.
- Backup history with success/failure information and Drive link.
- Admin-only access.

## Important
This is a normal custom Odoo addon containing Python code. It must be placed in an Odoo addons path and installed from Apps. It is not a data-only "Import Module" ZIP.

## Installation
1. Extract/copy the `ellaithy_drive_backup` folder into your custom addons directory.
2. Restart Odoo.
3. Update Apps List.
4. Search for **Ellaithy Google Drive Backup** and install it.

Example:
```bash
sudo cp -r ellaithy_drive_backup /opt/odoo/custom/Ellithy/
sudo chown -R odoo:odoo /opt/odoo/custom/Ellithy/ellaithy_drive_backup
sudo systemctl restart odoo
```

For Docker, copy/mount the addon into the addons path used by the Odoo container, then restart the container and update the app list.

## Google Cloud setup
1. Create or select a Google Cloud project.
2. Enable **Google Drive API**.
3. Configure the OAuth consent screen.
4. Create an OAuth 2.0 Client ID of type **Web application**.
5. Add this Authorized Redirect URI:
   `https://YOUR-ODOO-DOMAIN/ellaithy_drive_backup/oauth/callback`
6. In Odoo, open **Backup > Google Drive Backup**.
7. Enter Client ID and Client Secret. You may leave **Google Drive Folder ID** empty; the module will create its own **Odoo Backups** folder.
8. Save.
9. Click **Connect Google Drive** and authorize the Google account. If the OAuth app is in Testing mode, add this Google account under **Test users** in Google Cloud first.
10. Click **Test Google Drive**.
11. Click **Backup Now** to test.

## Notes
- The Odoo server must have a compatible `pg_dump` available. This is the same underlying requirement as Odoo's own database backup feature.
- ZIP mode uses Odoo's built-in backup service and includes the filestore.
- The temporary local backup is deleted after upload.
- Scheduled backups are checked every 15 minutes; the configured daily time may therefore run within the next cron check.
- `drive.file` scope is intentionally used rather than unrestricted Drive access. The selected destination folder must be accessible to the Google account and usable by files created through the app.

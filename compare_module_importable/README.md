CRM Marketing - Importable Odoo 18 Module

Install using Apps > Import Module. This package contains no executable Python model files.
After installation:
1. Assign Marketing Administrator to your user.
2. Open Marketing > Configuration > Settings and create one configuration record for the active company.
3. Select the CRM branch and profile/call-type fields.
4. Add marketing costs and source merge groups.
5. Open Marketing > Marketing Dashboard.

## Source field configuration
After upgrading, open Marketing > Configuration > Settings and select **CRM Source Field**. Choose the crm.lead field that actually stores the source in your database. The dashboard uses this configured field for Lead Inflow, Won Leads by Source, and Marketing Spend Intelligence.

Marketing Costs now loads the Source dropdown from that same configured CRM
field. Existing costs that used Odoo's standard Source field remain supported.

Source Merge Groups now uses the same configured field and supports selecting
multiple configured sources. Existing groups created with standard Odoo
sources remain supported and are migrated when edited.

## Version 18.0.3.0.4
- Source Merge Groups loads Sources from the configured CRM Source Field.
- Added searchable multi-source selection for merge groups.
- Merge rules now work with many2one, selection, and text source fields.
- Preserved groups created with the previous standard Odoo Sources field.

## Version 18.0.3.0.3
- Marketing Cost Source choices follow the configured CRM Source Field.
- Supports many2one, selection, and text-based CRM source fields.
- Keeps existing Marketing Cost source values compatible with the dashboard.


## Version 18.0.2.0.8
- Non-source tables now fill 100% of the dashboard width.
- Source and won-source matrices retain horizontal scrolling.
- Marketing Spend Intelligence uses the full available page width.


## Module visibility
Only users assigned **CRM Marketing / Marketing: Show Module** can see the Marketing app and dashboards. Cost Manager and Administrator imply this permission automatically.

# Ellaithy Marketing Analytics — Python Odoo 18 addon

Install this addon from the Odoo server addons_path, **not Apps > Import Module**.

## Install
1. Backup your Odoo database and filestore.
2. Copy `ellaithy_marketing_python/` to `/opt/odoo/custom/Ellithy/` (or your configured addons path).
3. Restart Odoo, Update Apps List, search **Ellaithy Marketing Analytics (Python)** and install.
4. Alternatively run `sudo -u odoo /usr/bin/odoo -c /etc/odoo/odoo.conf -d ellithy -i ellaithy_marketing_python --stop-after-init` if your instance runs from that binary and config.
5. Assign Marketing: User / Cost Manager / Administrator in user access rights.

## Existing importable module
This module uses new Python model names to avoid collisions with existing `x_compare.*` manual models. It does NOT automatically migrate old costs, source groups, or settings. Do not uninstall the old importable module before exporting/migrating its data. Do not keep both Marketing root menus enabled for the same users unless desired.

## Data and caveats
- Marketing analytics uses `crm.lead` and `utm.source`/`utm.campaign` data.
- Marketing costs are recorded per month. Filtering partial months includes the entire month's cost.
- Won counts represent the **current** won stage of leads created in the selected period, not the date they became won.
- CRM record rules and company access are respected. Currency conversions use Odoo rates.
- Large lead volumes should be optimized with read_group or SQL after testing on staging.
- The dashboard does not fabricate ad clicks, impressions, revenue, ROI or ROAS.

# Ellaithy POS (Odoo 18)

A backend POS/order-request workflow designed to work without Odoo's `point_of_sale` module.

## Workflow
Draft → Requested → Approved → ERP Confirmed → Invoiced → Done

- Users create requests and can only see their own requests.
- POS Managers approve/reject, create the ERP Sales Order, invoice it and close it after payment/delivery.
- Confirming in ERP creates and confirms a native `sale.order`, so Odoo handles stock reservations/deliveries and accounting/invoicing with standard ERP logic.

## Calculations
- Untaxed subtotal
- Taxes using native `account.tax.compute_all`
- Total
- Product cost
- Margin and margin percentage (manager only)
- Available stock per selected warehouse

## Permissions
- Ellaithy POS / POS User
- Ellaithy POS / POS Manager

## Install
Copy `ellaithy_pos` into the custom addons path, restart Odoo, update Apps List, then install **Ellaithy POS**.

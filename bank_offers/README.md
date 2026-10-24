# Bank Offers - Odoo 18 Python Custom Addon

This module contains Python models and must be installed from the server addons path.
It is **not** intended for Odoo's browser-based **Import Module** feature, because that import mechanism does not load Python model code.

## Technical name
`bank_offers`

## Main models
- `bank.offer.bank`
- `bank.offer.program`
- `bank.offer.rate`
- `bank.offer.job.type`
- `bank.offer.assessment`
- `bank.offer.assessment.result`

## Installation
1. Extract/copy the `bank_offers` folder to a configured custom addons directory.
2. Restart Odoo so Python models are loaded.
3. Update Apps List.
4. Install **Bank Offers**.

## Permissions
- Bank Offers User
- Bank Offers Configuration Manager

## 18.0.1.3.0
- Bank display/recommendation priority: ADIB, NBK, ABK, FAB, then other banks.
- Added FAB master bank record.
- Renamed sale-ban fee UI to مصاريف الحظر الإلكتروني and exposed it in results.
- Calculation now opens a result popup with installment months and today's date.
- Added PDF print action from the result popup.
- Added required Arabic terms and conditions to popup and PDF output.

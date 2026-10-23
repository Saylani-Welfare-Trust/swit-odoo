# Master Setup (`bn_master_setup`)

The **Master Setup** menu, and the lookup lists that many modules share.
It has no workflow of its own.

**Depends on:** `base`, `mail`, `product`, `stock`, `account`

## Shared masters

| Model | Used by |
| --- | --- |
| `city` | Profile Management, Welfare, Qurbani, Medical Equipment, Import Donation |
| `bank` | POS (cheques, payment methods, closing session), Direct Deposit, Advance Donation, Welfare, bank reconciliation |
| `area` | Profile Management, Welfare, Medical Equipment |

## Feature configuration lives in its own module

Every feature module keeps its own models, views and data, and only places
its configuration menu under *Master Setup* (as Donation Box does with
*Installation Category*):

| Configuration | Module |
| --- | --- |
| Microfinance schemes, loan products, installments, security types | `bn_microfinance` |
| Qurbani days, Hijri year, Chand Raat | `bn_qurbani` |
| Disbursement categories / application types | `bn_welfare` |
| Medical equipment categories | `bn_medical_equipment` |
| Direct deposit account prefix | `bn_direct_deposit` |
| Advance donation categories | `bn_advance_donation` |
| Installation categories | `bn_donation_box` |
| Profile types (tags), areas editing for profile managers | `bn_profile_management` |
| Location options, sub zones | `bn_analytic_account_customization` |

In 17.0.1.2.0 the stale copies of those models that were still in this
module (not loaded since 29 Sep 2026) were removed, as well as three unused
ones: `product.master`, `qurbani.hijri` and `sms.template`.

## Security groups

| Group | Can |
| --- | --- |
| *Access Root Menu* | See the Master Setup menu (implied by every group below, and by the managers / auditors of the feature modules) |
| *User* | Read City, Bank and Area |
| *Manager* | Create and edit City, Bank and Area |
| *Audit* | Read-only |
| *Admin* | Everything, including delete |
| *Menu (legacy)* | Former single group; gives the menu only |

Every internal user can read City, Bank and Area, so the forms of other
modules can select them.

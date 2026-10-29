# Microfinance (`bn_microfinance`)

Interest-free loans to registered donees: as cash, or as
an asset (motorbike, rickshaw, sewing machine ...) repaid in monthly or
daily installments. Security deposits, installments and recoveries are
received at the Point of Sale.

**Depends on:** `bn_master_setup`, `bn_profile_management`, `bn_pos_order`,
`bn_advance_donation`, `bn_pos_custom_action`, `bn_pos_cheque`, `sale_stock`,
`report_xlsx`

## Main models

| Model | What it is |
| --- | --- |
| `microfinance` | One loan application (applicant, scheme, product, amounts, documents, guarantors, family, status) |
| `microfinance.line` | One installment of the repayment plan (due date, amount, paid, cheque) |
| `microfinance.recovery.line` | Installments of a loan sent to recovery |
| `microfinance.installment` | A receipt: **SD slip** (security deposit) or installment receipt |
| `microfinance.pdc.line` | Post-dated cheques |
| `microfinance.scheme` / `.scheme.line` | Schemes and what they finance (cash, movable asset, immovable asset) |
| `loan.product.line` / `loan.product.installment` | Product of a scheme line: SD amount, installment amount, allowed numbers of installments |
| `security.offered` | Security types (guarantor, collateral ...) |
| `return.microfinance.product` (wizard) | Takes a recovered asset back into stock |
| `microfinance.application.wizard` | From a registered donee's profile: picks the scheme, creates the Draft loan and prints the application form (moved here from `bn_profile_management` in 17.0.1.2.0) |

## Process flow

```mermaid
flowchart TD
    A([User: loan application<br/>donee, scheme, product, installments]) --> D[Draft]
    D -->|Move to HOD, User| H[HOD Approval]
    H -->|Move to Member, HOD| M[Member Approval]
    H -->|Revert, HOD| D
    M -->|Revert, Member| H
    H & M -->|Reject + remarks| RJ([Rejected])
    M -->|Approve, Member<br/>prints approval certificate| AP[Approved]
    AP -->|SD Slip| SD[SD slip<br/>paid at the POS]
    SD -.->|required before disbursement| AP
    AP -->|Cash: Move to Treasury| T[Treasury<br/>vendor bill, no tax]
    T -->|Accounts pays the bill| DONE
    AP -->|Asset: Proceed<br/>sale order + delivery| W[Waiting For Delivery]
    W -->|Warehouse validates the delivery<br/>immovable: Move to Done| DONE[Done<br/>installment plan created]
    DONE -->|installments paid at the POS| DONE
    DONE -->|Send for Recovery| R[In Recovery]
    R -->|Temporary Recovered, Recovery<br/>asset taken back to stock| TR[Temp Recovered]
    TR -->|Fully Recovered| FR[Fully Recovered]
    FR -->|Write Off Request| W1[Write Off Approval 1]
    W1 -->|Approve, Approver 1| W2[Write Off Approval 2]
    W2 -->|Approve, Approver 2| RG([Right Granted])
    W1 & W2 -->|Reject| FR
```

Every button checks the loan's status and the user's role on the server;
the status cannot be written directly.

- **Security deposit first:** a loan with a security deposit is only
  disbursed (Move to Treasury / Proceed) once its SD slip is **paid**.
- **Cash loans:** the vendor bill is for the loan amount (no purchase tax).
  When Accounts pays it, the loan is Done and its installments are created.
- **Asset loans:** Proceed checks the warehouse location really has the
  asset, then creates and confirms the sale order; validating its delivery
  completes the loan. Warehouse and Accounts staff need no Microfinance
  rights for this.
- **Post-dated cheques:** the PDC template columns are *Installment ID,
  Cheque Number, Bank Name, Amount, Cheque Date*. The upload only accepts
  installments of the loan itself.

## Point of Sale

POS cashiers (role *POS Action*) receive the security deposit, installments
and recoveries through the POS *Action* button (`bn_pos_custom_action`).

All the microfinance POS code is in this module (`static/src/`); it plugs
into the shared screens of `bn_pos_custom_action` through hooks:

| File | What it does |
| --- | --- |
| `app/action_button` | Loads the *POS Action* right of the cashier |
| `app/action_screen` | The **Microfinance** button and its menu |
| `app/provisional_popup` | Security deposit: request no., SD product added to the order (`confirmProgram` hook) |
| `app/receiving_popup` | Installment / recovery: loads the unpaid lines (`confirmProgram` hook) |
| `screens/payment_screen.js` | After the order is **saved**: marks the SD slip paid, spreads the payment over the installment lines, pays the recovery lines |

The loan is only updated once the POS order is validated and saved; a
cancelled or failed validation leaves it untouched. If the update itself
fails, the cashier gets a message to inform the Microfinance team.

Also in this module: the company fields *Microfinance Installment /
Security Deposit* (product names used by the POS), the POS cheque hooks
(clearing, bouncing or cancelling a post-dated cheque updates its PDC line
and installment) and the `microfinance_id` link on advance donation
disbursement lines.

## Security groups

| Group | Can |
| --- | --- |
| *Access Root Menu* | See the app (implied by every tier) |
| *User* | Create applications, send them to the HOD, SD slips and receipts, Proceed / Move to Treasury / Move to Done, Send for Recovery |
| *Manager* | User + configuration under *Master Setup > Microfinance* |
| *Audit* | Read-only, everything |
| *Administrator* | Everything, delete |

Roles (category *Microfinance Roles*, added on top of a tier; each implies
*User*): **HOD** (move to Member, reject, revert), **Member** (approve,
reject, revert to HOD), **Recovery** (recovery steps, write-off request),
**Write Off Approval 1 / 2**, and **POS Action** (POS cashiers: no access to
the app itself, only what the POS needs).

## What changed in 17.0.1.3.0

| Problem | Fix |
| --- | --- |
| Microfinance POS code, company fields and cheque handling were in `bn_pos_custom_action` / `bn_pos_cheque`, which do not depend on this module | Moved here, plugged in through hooks |
| POS marked installments / the SD slip paid **before** the order was saved | Only after the order is saved |
| POS recovery refused every loan ("Unauthorized Request State"): it required *Done*, but a loan with recovery lines is *In Recovery* | Accepts *In Recovery* |
| Recovery lines copied the paid amount of the installments but not their status | Status copied |
| Installment / recovery receipt still closed the popup when the lines could not be loaded | Stops with the message |
| SD added without its product when the product was missing | Error shown, nothing added |
| The POS Shariah check could never run (it read a field of a record id string) | Removed; the Shariah sync checks the balance on the server |

## What changed in 17.0.1.1.0

| Problem | Fix |
| --- | --- |
| Loans readable, editable and deletable by **every user, including portal** (access rules without group) | Rules per group |
| No status checks: a Draft loan could be approved, written off ... by anyone | Status + role checked on the server; status only through the buttons |
| Member could not Reject / Revert (buttons only shown at HOD Approval) | Shown at Member Approval |
| POS security deposit payment always failed ("schedule line not found") | Uses the SD slip |
| Loans disbursed without the security deposit received | Required |
| Cash loan bill added purchase tax (51,750 for a 45,000 loan) | No tax |
| Asset stock check searched a non-searchable field | Checks the quantity at the warehouse location |
| Asset loans needed Inventory rights for the User; the Recovery wizard and Temporary Recovered needed admin rights; warehouse / Accounts users could not complete loans | Fixed |
| Landlord CNIC field crashed when edited | Fixed |
| PDC upload read the cheque date from the Amount column and could write to another loan's installments | Fixed |
| Security type "Applications" button opened an invalid filter | Fixed |
| Line / receipt numbers overwrote any name given | Only when empty |
| Re-applying after a rejected loan was blocked (`bn_profile_management` checked a non-existing status) | Fixed |
| `bn_pos_order` could not be installed (list view referenced a field missing from it); `bn_pos_order`, `bn_advance_donation`, `bn_microfinance` lacked dependencies they use | Fixed |

## Tests

`tests/test_microfinance.py` (approval roles, cash loan, asset loan with
delivery / recovery / write off, PDC upload), run with:

```bash
odoo-bin -d <db> -u bn_microfinance --test-enable --test-tags /bn_microfinance --stop-after-init
```

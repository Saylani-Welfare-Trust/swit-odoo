# Approval Cycle for Odoo 17

One module covers every Odoo model. A rule names the model and the button to protect. Sales, purchase, expenses, time off, manufacturing, repairs, and custom models all use the same setup.

> Exercised against a live Odoo 17 database. Install this module and turn on the master switch.

## Setup
1. *Settings > Approval Cycle*: turn on the master switch. Turn on Department-wise Approval when HOD should follow the department tree.
2. *Approval Roles*: HOD resolves the department manager, then each different parent manager when **Include Parent Department Managers** is on. Set users or a security group on Internal Audit, Taxation, COO, CFO, and CEO, then activate those roles.
3. *Approval Rules*: search the target model by its name (Sales Order, Purchase Order, Journal Entry). Pick the button from the list on that form, for example Confirm (`action_confirm`). Add stages. Leave a stage on Always to ask that role for every amount. Set Required When to Amount Threshold to enter the only minimum and maximum for that stage. Roles do not have their own amounts.

## What a click does
- The button does not confirm the record yet. It creates a request for the first stage and hides that button on the document.
- Approving a stage creates the next request: sub-department manager, then parent managers, then the named roles that apply.
- The last approval runs that same button, with the original user's rights.
- The document shows an **Approvals** smart button for its requests.

Limits: only public business buttons can be protected (`write`, `create`, and `unlink` cannot). The amount comes from `amount_total`, `total_amount`, or `amount`, and from quantity times cost on a manufacturing order. Use an Always stage when the document has no amount.

# Rider Shift (`bn_rider_shift`)

Plans the riders who visit installed donation boxes, records what each
rider collected from each box, and sends the money to the Point of Sale for
a receipt. It also handles counterfeit notes (**CFB**) and foreign currency
(**FCB**) found in the boxes.

**Depends on:** `bn_key_management`, `bn_donation_box`

## Main models

| Model | What it is |
| --- | --- |
| `rider.shift` | A rider's shift for a date range (Draft → Done) |
| `rider.schedule.day` | One planned day of a shift: city, zone, sub zone, key bunch, number of keys |
| `rider.collection` | One box to collect for one rider on one date. Created when the box's key is issued |
| `rider.schedule` / `rider.schedule.line` (wizard) | The rider's **Check Shift** screen: open collections to work on |
| `counterfeit.notes` | Counterfeit notes found in a box (Draft → Payment Received → Paid) |
| `foreign.currency` | Foreign notes found in a box (Draft → Converted / Reject) |
| `counterfeit.notes.wizard`, `foreign.currency.wizard` | Turn CFB / FCB lines into a POS collection |

## Process flow

```mermaid
flowchart TD
    S([Rider Shift + schedule days<br/>which key bunch on which day]) -->|key officer issues the bunch for the day| I[Key Issuance per key<br/>bn_key_management]
    I --> C[Rider Collection per box<br/>Donation not collected]
    C -->|Rider opens Check Shift| W{For each box}
    W -->|Mark as Done| D[Donation collected]
    D -->|enter amount, counterfeit,<br/>foreign notes → Submit| SUB[Donation submit]
    W -->|remarks → Pending| P[Pending<br/>key issuance → Pending]
    W -->|box status + remarks →<br/>Generate Complaint| CC[Complaint in Draft<br/>bn_donation_box]
    SUB -->|counterfeit > 0| CN[Counterfeit Notes: Draft]
    SUB -->|Change Rate| FC[Foreign Currency lines: Draft]
    SUB --> POS[POS → Actions → Donation Box<br/>amount must match]
    POS --> PAID[Collection: Paid<br/>issuance: Donation Received]
    PAID --> RET[Key returned to the bunch]
```

### Counterfeit and foreign currency

```mermaid
flowchart LR
    CN[Counterfeit Notes<br/>Draft] -->|select notes → Create CFB| CFB[Collection 'CFB'<br/>Donation submit]
    FC[Foreign Currency<br/>Draft] -->|Convert| FCC[Converted]
    FC -->|Reject| FR[Reject]
    FCC -->|select lines of one box →<br/>Create POS record| FCB[Collection 'FCB'<br/>Donation submit]
    CFB --> POS[POS deposit]
    FCB --> POS
    POS --> PD[Collection and notes: Paid<br/>posted to Counterfeit / Foreign Currency Donor]
```

## Collection statuses

Donation not collected → Donation collected → Donation submit → Paid,
or → Pending.

## Rules

- Only users in **Rider Collection / Edit Amount / Notes** can change the
  amount or counterfeit amount of a collection. Only users in
  **Foreign Currency Collection** can change a foreign currency amount.
- A pending box needs remarks and an active key issuance for that date.
- A generated complaint stays in Draft until the Complain Officer processes
  it in the Complain Center. A box taken out of service (registration
  Closed) cannot get a complaint.
- When a Box No. was reused after the box was taken out of service, *Pending*,
  FCB and CFB use the registration and key **in service**, never the closed
  ones (17.0.1.2.0; before, *Pending* failed and FCB / CFB could post to the
  old registration).

## Tests

`tests/test_closed_box.py` covers a box taken out of service and its Box No.
reused; `tests/test_roles.py` runs each step of the flow as the role that
owns it (Donation Box User / Manager, Key Management User, Rider, Audit).
Both cover `bn_donation_box`, `bn_key_management` and this module:

```bash
odoo-bin -d <db> -u bn_rider_shift --test-enable --test-tags /bn_rider_shift --stop-after-init
```

The tests are `post_install`. Run them on a database where the modules are
already upgraded (or run the command twice): during the upgrade run itself,
`key.issuance.rider_collection_id` is not resolved yet, because
`rider.collection` is defined in this module.

## Added to Key Management

This module adds to `key.issuance`: `rider_collection_id`, the rider
collection created when a key is issued, and the POS RPC
`set_donation_amount`. The POS **Donation Box** popup and its payment check
are in `static/src/`. The bulk key wizard only offers the riders and key
bunches scheduled for the day.

## Security groups

| Group | Menus | Buttons / actions |
| --- | --- | --- |
| *Access Root Menu* | Rider (implied by every group) | - |
| *User* | Shift, Collection, **Schedule**, Counterfeit Notes, Foreign Currency | Report own collection (Done / Pending / Submit, Complain Center), **Move to Done**, **Convert** / **Reject** / **Create POS Order** (FCB), **Create CFB** |
| *Rider Collection / Edit Amount / Notes* | - | Change the amount / counterfeit notes of a collection afterwards |
| *Foreign Currency Collection* | - | Change the amount of a foreign currency entry |
| *Manager* | Same as User | User + both edit groups above + report any rider's collection |
| *Audit* | All except Schedule, read-only | None |
| *Admin* | Same | Everything |

**Riders report their own collections** in *Schedule*: the amount they
enter is written to the collection although they cannot edit a collection's
amount directly. A rider can only report collections of their own employee
(a Manager can report any), and only while the collection is open (not yet
submitted or pending). Marking Pending, raising a complaint, FCB and CFB
update keys, issuances and complaints without needing Key Management or
Donation Box rights. Riders can read the registrations, keys and issuances
of their boxes.

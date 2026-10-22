# Key Management (`bn_key_management`)

Tracks the physical key of every installed donation box: where the key is
stored (key bunch), which rider has it, and whether the rider brought back
the money and the key.

**Depends on:** `bn_donation_box`

## Main models

| Model | What it is |
| --- | --- |
| `key` | One key per box (serial). Created automatically when a donation box request is approved |
| `key.bunch` | A physical ring of keys (room / rack / shelf / slot, city, zone, sub zone). Max **50** open keys per bunch |
| `key.issuance` | A key handed to a rider for a given date |
| `bulk.key.issuance` (wizard) | Issue or return a whole bunch to / from a rider |
| `manual.key.issuance` (wizard) | Issue or return a single key |

It also extends the donation box registration with the key bunch, and
implements the key hooks used by `bn_donation_box` (create, activate,
change request, close, "can this box be released?").

## Process flow

```mermaid
flowchart TD
    A([Donation Box Request approved]) --> B[Key created<br/>status: Draft]
    B -->|Registration approved<br/>with a Key Bunch| C[Key: Available<br/>stored in the bunch]
    C -->|Bulk or manual issuance<br/>to a rider for a date| D[Issuance: Issued<br/>Key: Issued]
    D -->|also creates| RC[Rider Collection<br/>bn_rider_shift]
    D -->|daily cron, no donation yet| E[Issuance: Overdue]
    D -->|rider marks the box Pending| F[Issuance: Pending<br/>Key: Pending]
    E --> F
    D -->|amount deposited on POS| G[Issuance: Donation Received]
    E -->|amount deposited on POS| G
    F --> G
    G -->|Return key| H[Issuance: Returned<br/>Key: Available]
    F -->|Return key| H
    H -->|next issuance| D
    C -->|registration closed:<br/>return / scrap / lost| X[Key: Closed]
```

### POS: recording the collected amount

```mermaid
sequenceDiagram
    participant Rider as Cashier / Rider
    participant POS
    participant Odoo as key.issuance.set_donation_amount
    Rider->>POS: Actions → Donation Box
    POS->>Odoo: list submitted collections (rider.collection)
    Rider->>POS: pick box, enter amount
    POS->>Odoo: check_validation = true
    Odoo-->>POS: OK + donor of the box
    POS->>POS: add Donation Box product, set donor
    Rider->>POS: Validate payment
    POS->>Odoo: check_validation = false
    Odoo->>Odoo: amount must equal the submitted collection<br/>issuance → Donation Received, collection → Paid
```

Collections marked **CFB** (counterfeit notes) or **FCB** (foreign currency)
are posted to a "Counterfeit Donor" / "Foreign Currency Donor" partner and
their issuance is closed directly.

## Rules

- A key can be issued only when it is **Available** and has no other open
  issuance. Concurrent issue/return operations lock the key row.
- Keys and issuances cannot be deleted. They are closed by the workflow.
- A bulk issuance is refused while any key of the bunch is still out.
- Only issuances in *Donation Received* or *Pending* can be returned.
- Scheduled action **Hit Overdue Action | BN** (daily) turns *Issued*
  issuances with no donation into *Overdue*.

## Security groups

*Access Root Menu*, *User*, *Manager*, *Audit*, *Admin*.

# Advance Donation Integration for Welfare Module

## Overview

This implementation adds comprehensive support for integrating advance donations into welfare lines and recurring lines. The system automatically manages donation line reservations, validates product matching, and prevents negative amounts.

## Features Implemented

### 1. **Welfare Line Integration** (`welfare_line_sync.py`)

#### Auto-Selection of Donation Lines
When a welfare line has a product assigned and an advance donation is selected:
- The system automatically searches for available donation lines with the same product
- The first available donation line is auto-selected
- If no matching lines are available, the user is alerted with detailed information

#### Validation Logic
Product matching ensures safety and prevents errors:
- **Product Mismatch Check**: Validates that the welfare line product matches the donation line product
- **Disbursement Check**: Ensures the donation line hasn't been disbursed already
- **Reservation Check**: Verifies the donation line isn't reserved by another welfare line
- **Amount Validation**: Ensures the donation line amount doesn't exceed the welfare line total amount (prevents negative totals)

#### Automatic Amount Adjustment
The welfare line's total amount is automatically reduced by the reserved donation line's amount:
```
Final Total Amount = (Quantity × Unit Price) - Donation Line Amount
```
The system ensures this never goes below 0.

#### Reservation System
Once a donation line is selected:
- The donation line is **reserved** for this specific welfare line (`reserved_welfare_line_id`)
- The reservation is **automatic** when the user selects the donation line
- The reservation is **cleared** if a different donation line is selected
- The system **logs** all reservation changes for audit trail

### 2. **Recurring Line Integration** (`welfare_recurring_line_sync.py`)

#### Auto-Assignment to Recurring Lines
When recurring lines are created with an advance donation:
- The system identifies available donation lines (excluding the one reserved by the main welfare line)
- Available donation lines are automatically distributed to recurring lines using round-robin distribution
- Multiple recurring lines CAN share the same donation line from the available pool
- If 3 recurring lines are created and 5 donation lines are available, they use lines in sequence: 1→1, 2→2, 3→3 (cycling)

#### Reservation for Recurring Lines
Recurring lines use a **Many2many** relationship with donation lines:
- One donation line can be reserved by multiple recurring lines
- Each recurring line has its own entry in `reserved_welfare_recurring_line_ids`
- Prevents collision between welfare line and recurring line reservations

#### Smart Filtering
The domain for donation lines automatically filters to:
- Exclude lines reserved by the main welfare line (`reserved_welfare_line_id = False`)
- Include only lines not disbursed (`is_disbursed = False`)
- Match the product (`product_id` must match recurring line product)
- Allow sharing between recurring lines (Many2many)

### 3. **Amount Tracking**

Both welfare and recurring lines track the donated amount:
```python
used_from_advance_donation_amount = donation_line.amount (if assigned)
total_amount_after_donation = base_total - used_from_advance_donation_amount
```

### 4. **Error Handling & User Feedback**

Comprehensive error messages inform users of issues:

**Product Mismatch**
```
❌ Product Mismatch!

Welfare Line Product: Wheelchair
Donation Line Product: Crutches

Both must have the same product to reserve this donation line.
```

**Already Disbursed**
```
❌ Donation Line Already Disbursed!

Line: DNL-001
Amount: 50,000

This donation line has already been disbursed and cannot be reserved.
```

**Amount Exceeds Total**
```
❌ Amount Validation Error!

Welfare Line Base Amount (Qty × Price): 100,000
Donation Line Amount: 150,000

Donation amount cannot exceed total amount.
Final amount would be: -50,000
```

**No Available Lines**
```
❌ No available donation lines for product Wheelchair:
  Total lines: 10
  Disbursed: 5
  Reserved by welfare line: 3
  Product mismatch: 2
```

## Data Model Changes

### New Fields in `welfare.line`

| Field | Type | Description |
|-------|------|-------------|
| `advance_donation_id` | Many2one | Link to advance donation |
| `advance_donation_line_id` | Many2one | Specific donation line reserved |
| `advance_donation_line_domain` | Char (computed) | Dynamic domain filter for available lines |
| `used_from_advance_donation_amount` | Float (computed) | Amount from donation line |

### New Fields in `welfare.recurring.line`

| Field | Type | Description |
|-------|------|-------------|
| `advance_donation_id` | Many2one | Link to advance donation |
| `advance_donation_line_id` | Many2one | Specific donation line reserved |
| `advance_donation_line_domain` | Char (computed) | Dynamic domain filter for available lines |
| `used_from_advance_donation_amount` | Float (computed) | Amount from donation line |

### Extended Fields in `advance.donation.lines`

| Field | Type | Description |
|-------|------|-------------|
| `reserved_welfare_line_id` | Many2one | Welfare line that reserved this line |
| `reserved_welfare_recurring_line_ids` | Many2many | Recurring lines that reserved this line |
| `is_reserved` | Boolean (computed) | Whether this line is reserved by any welfare |
| `reserved_by_record_name` | Char (computed) | Name of the welfare record that reserved it |

## Workflow Example

### Scenario: Medical Equipment with 3-Month Recurring Support

1. **Main Welfare Order Created**
   - Product: Wheelchair
   - Quantity: 1
   - Unit Price: 100,000
   - Total Amount: 100,000

2. **Advance Donation Attached**
   - User selects Advance Donation "AD-001"
   - System auto-finds donation line (DNL-001, Amount: 40,000, Product: Wheelchair)
   - **Result**: 
     - Donation line DNL-001 reserved for main welfare
     - Total amount adjusted: 100,000 - 40,000 = 60,000

3. **Recurring Lines Created** (3 months)
   - Three recurring lines created with same advance donation
   - System identifies available lines: DNL-002, DNL-003, DNL-004 (each 30,000)
   - **Auto-assignment**:
     - Recurring Month 1 → DNL-002 (30,000 reserved)
     - Recurring Month 2 → DNL-003 (30,000 reserved)
     - Recurring Month 3 → DNL-004 (30,000 reserved)
   - Each recurring line's total: 100,000 - 30,000 = 70,000

## Implementation Details

### Auto-Selection Flow

```
User selects Advance Donation
        ↓
System searches for available lines with matching product
        ↓
Available? ───No──→ Clear selection, log warning
   ↓ Yes
Auto-select first available line
        ↓
Validate product match, amount, and disbursement status
        ↓
Success ──→ Update UI with selected line
   ↓ Fail
Show error message
```

### Recurring Line Assignment Flow

```
Recurring lines created with Advance Donation
        ↓
Get welfare's main line reserved donation
        ↓
Get remaining available donation lines (exclude main line)
        ↓
For each recurring line:
  Calculate index (ID % available count)
  Assign corresponding donation line
  Log reservation
        ↓
Complete
```

### Amount Calculation

```
Base Total Amount = Quantity × Unit Price
Donation Amount = selected_donation_line.amount
Final Total Amount = Max(0, Base Total Amount - Donation Amount)
```

## Logging & Audit Trail

All reservation changes are logged with timestamps:

```
[INFO] Auto-selected donation line DNL-001 (Amount: 40,000) for welfare product Wheelchair
[INFO] Reserved donation line DNL-001 (Amount: 40,000) for welfare line Welfare/001
[INFO] Auto-assigned donation line DNL-002 (Amount: 30,000) to recurring line 1
[INFO] Released recurring line 1 from donation line DNL-002
```

## Collision Prevention

The system prevents collisions through:

1. **Single Reservation per Welfare Line**: 
   - Only one donation line can be reserved by `welfare.line` at a time
   - Clearing previous reservation before setting new one

2. **Multiple Reservations per Donation Line**:
   - Donation lines can be reserved by multiple recurring lines (Many2many)
   - Prevents donation lines from being locked to a single recurring line

3. **Exclusive Welfare vs Recurring**:
   - Donation lines reserved by welfare line (`reserved_welfare_line_id`) cannot be used by recurring lines
   - Ensures main welfare line always has its dedicated donation source

4. **Disbursement Lock**:
   - Once donated amount is disbursed (`is_disbursed = True`), no further reservations allowed

## Usage Instructions

### For Welfare Line Users

1. **Create Welfare Line**
   - Select product and quantity

2. **Attach Advance Donation**
   - Select an advance donation from the dropdown
   - System auto-selects first available matching line

3. **Verify Amount**
   - Total amount is automatically adjusted
   - Review the reduction in total amount

### For Managers

1. **Monitor Reservations**
   - Check `reserved_by_record_name` field to see which welfare is using each donation line
   - Review `is_reserved` status for quick overview

2. **Audit Trail**
   - Check server logs for all reservation changes
   - Track which user made which donation line selections

### Configuration (in `res.company`)

No special configuration needed. System uses existing:
- Product definitions
- Advance donation records
- Welfare/recurring line structures

## Edge Cases Handled

1. **No Product on Welfare Line**: Auto-selection skipped until product is set
2. **Product Changed**: Auto-selection recalculates with new product
3. **Quantity Changed**: Amount validation re-runs (may trigger error if total becomes too low)
4. **All Donation Lines Disbursed**: User informed with detailed count breakdown
5. **Multiple Matching Lines**: First line (by ID) auto-selected, user can manually change
6. **User Manually Selects Line**: Validations run, error shown if any fail
7. **Recurring Lines Exceed Available Lines**: Round-robin ensures all get assigned (cycling through available)

## Performance Considerations

- **Computed Fields**: `advance_donation_line_domain` computed and stored for performance
- **Indexes**: Consider adding indexes on `reserved_welfare_line_id` and `is_disbursed` in production
- **Search Optimization**: Queries use `limit=1` where appropriate
- **Logging**: Info/Warning level logging only, no excessive debug output

## Future Enhancements

1. **Batch Assignment**: Bulk assign donation lines to multiple welfare orders
2. **Dashboard**: Visual representation of donation line utilization
3. **Reports**: Advanced donation usage by welfare type/product
4. **Alerts**: Notify when certain products have limited donation availability
5. **Forecasting**: Predict donation line shortages based on trends

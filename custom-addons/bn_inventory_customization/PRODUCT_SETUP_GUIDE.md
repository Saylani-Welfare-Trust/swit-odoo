# Complete Product Setup Guide for Weight-Based Livestock Receiving

## Understanding the Product Structure

This module uses a **DUMMY + REAL** product pattern:

### 1. DUMMY PRODUCT (Purchase Product)
- **Purpose:** Used in Purchase Orders only
- **What it is:** A simple product (can be with or without variants)
- **Key Configuration:**
  - `Is Livestock Product (check_stock)` = ✅ **TRUE**
  - `Main Attribute` = Set to your Weight Range attribute
  - `Livestock Variant` = Leave **EMPTY** (or can be set, but typically empty)
  - `Purchase Product` = Leave **EMPTY** (it doesn't point to itself)

**Example Dummy Product:**
- Name: "Camel - Purchase - Medium Weight"
- Cost: 150 per kg
- check_stock: TRUE
- This product appears in PO only, never appears in final stock

---

### 2. REAL PRODUCTS (Stock Products with Variants)
- **Purpose:** These are the actual products added to stock after receiving
- **What it is:** Product templates with variants for different weight ranges
- **Key Configuration:**
  - `Is Livestock Product (check_stock)` = ✅ **TRUE**
  - `Purchase Product` = Points to the DUMMY product above
  - `Livestock Variant` = Set to specific variant (e.g., "Sadqa", "Aqiqa", "Qurbani")
  - `Main Attribute` = Set to your Weight Range attribute
  - **Must have variants** with weight range attribute values

**Example Real Products:**

#### Product A: "Camel - Sadqa (Storable)"
- check_stock: TRUE
- purchase_product: "Camel - Purchase - Medium Weight" (the dummy)
- livestock_variant: "Sadqa"
- main_attribute_id: "Weight Range"
- Variants:
  - Camel - Sadqa - Small (10-20 kg)
  - Camel - Sadqa - Medium (20-30 kg)
  - Camel - Sadqa - Large (30-50 kg)
  - Camel - Sadqa - Extra Large (50-100 kg)

#### Product B: "Camel - Aqiqa (Storable)"
- check_stock: TRUE
- purchase_product: "Camel - Purchase - Medium Weight" (same dummy)
- livestock_variant: "Aqiqa"
- main_attribute_id: "Weight Range"
- Variants: (same weight ranges as above)

#### Product C: "Camel - Qurbani (Storable)"
- check_stock: TRUE
- purchase_product: "Camel - Purchase - Medium Weight" (same dummy)
- livestock_variant: "Qurbani"
- main_attribute_id: "Weight Range"
- Variants: (same weight ranges as above)

---

## Step-by-Step Setup

### Step 1: Create Livestock Variants
Go to: **Inventory > Configuration > Livestock Variants**

Create:
- Sadqa
- Aqiqa
- Qurbani
(Already created via demo data)

### Step 2: Create Weight Range Attribute
Go to: **Inventory > Configuration > Products > Attributes**

1. Create attribute: "Weight Range"
2. Display Type: "Radio"
3. Variants: "Instantly" (to create variants)
4. Add Values with weight ranges:
   - Small: from_kg = 10, to_kg = 20
   - Medium: from_kg = 20, to_kg = 30
   - Large: from_kg = 30, to_kg = 50
   - Extra Large: from_kg = 50, to_kg = 100

(Already created via demo data)

### Step 3: Create DUMMY Product (Purchase Product)

1. Go to: **Purchase > Products > Products > Create**
2. Fill in:
   - Name: "Camel - Purchase"
   - Product Type: "Storable Product"
   - Cost: 150 (per kg base price)
   - ✅ Check "Is Livestock Product (check_stock)"
3. In "Livestock Configuration" section:
   - Main Attribute: "Weight Range"
   - Purchase Product: (leave empty)
   - Livestock Variant: (leave empty or set to default)
4. Save

### Step 4: Create REAL Products (Stock Products)

**For Sadqa:**

1. Go to: **Purchase > Products > Products > Create**
2. Fill in:
   - Name: "Camel - Sadqa"
   - Product Type: "Storable Product"
   - ✅ Check "Is Livestock Product (check_stock)"
3. In "Livestock Configuration" section:
   - Main Attribute: "Weight Range"
   - **Purchase Product:** Select "Camel - Purchase" (the dummy)
   - **Livestock Variant:** Select "Sadqa"
4. Go to "Attributes & Variants" tab
5. Add attribute: "Weight Range"
6. Select all weight values (Small, Medium, Large, Extra Large)
7. Odoo will automatically create 4 variants:
   - Camel - Sadqa (Small)
   - Camel - Sadqa (Medium)
   - Camel - Sadqa (Large)
   - Camel - Sadqa (Extra Large)
8. Save

**Repeat for Aqiqa and Qurbani** with the same structure.

---

## Complete Workflow Example

### Scenario: Purchase 5 camels

**Step 1: Create Purchase Order**
- Partner: Your Vendor
- Product: "Camel - Purchase" (DUMMY)
- Quantity: 5
- Price will auto-calculate based on base price × max weight multiplier

**Step 2: Confirm PO**
- Odoo creates receipt

**Step 3: Validate Receipt**
- Click "Validate" button
- Dummy product "Camel - Purchase" temporarily added to stock (5 units)
- "Receive by Weight" button appears

**Step 4: Open Wizard**
- Click "Receive by Weight"
- Wizard shows 5 lines (one per camel)
- Each line shows: S.No, Product (dummy), Livestock Variant dropdown, Weight field

**Step 5: Enter Actual Data**
| S.No | Product | Livestock Variant | Weight (kg) |
|------|---------|-------------------|-------------|
| 1 | Camel - Purchase | Sadqa | 25 |
| 2 | Camel - Purchase | Sadqa | 18 |
| 3 | Camel - Purchase | Aqiqa | 45 |
| 4 | Camel - Purchase | Qurbani | 55 |
| 5 | Camel - Purchase | Qurbani | 32 |

**Step 6: Click "Receive"**

System automatically:
1. Searches for product with purchase_product="Camel - Purchase" + livestock_variant="Sadqa"
   - Finds: "Camel - Sadqa"
2. For weight 25 kg, finds variant in range 20-30 kg
   - Matches: "Camel - Sadqa (Medium)"
3. Removes 1 unit of "Camel - Purchase" from stock
4. Adds 1 unit of "Camel - Sadqa (Medium)" to stock

Repeats for all 5 lines.

**Final Stock Result:**
- Camel - Purchase: 0 units (removed)
- Camel - Sadqa (Medium): 1 unit (25 kg)
- Camel - Sadqa (Small): 1 unit (18 kg)
- Camel - Aqiqa (Large): 1 unit (45 kg)
- Camel - Qurbani (Extra Large): 1 unit (55 kg)
- Camel - Qurbani (Large): 1 unit (32 kg)

---

## Button Visibility Rules

**"Receive by Weight" button appears when:**
- ✅ Receipt is validated (state = 'done')
- ✅ At least one product on receipt has `check_stock = True`

**Button is hidden when:**
- ❌ Receipt not validated yet (draft/assigned)
- ❌ No livestock products on receipt

---

## Troubleshooting

### Error: "No product template found that links purchase_product..."

**Cause:** You're trying to receive with a product that doesn't have matching real products.

**Solution:**
1. Check the error message shows which dummy product and livestock variant it's looking for
2. Create a real product (storable) with:
   - check_stock = TRUE
   - purchase_product = the dummy product mentioned in error
   - livestock_variant = the variant mentioned in error
   - Must have variants with weight ranges

### Error: "No matching variant found in range X kg..."

**Cause:** The weight you entered doesn't fall within any attribute value range.

**Solution:**
1. Check your Weight Range attribute values
2. Ensure from_kg and to_kg cover the weight you entered
3. Example: If you enter 25 kg, you need a range like 20-30 kg

### Button doesn't appear after validation

**Solution:**
1. Ensure dummy product has `check_stock = True`
2. Upgrade the module after making changes
3. Check if `show_receive_by_weight` field is computed correctly

---

## Key Differences from Original bn_live_stock_grn

This implementation (`bn_inventory_customization`) is an exact replica of `bn_live_stock_grn` with:
- Same product structure (dummy + real)
- Same workflow (validate → wizard → receive by weight)
- Same logic (remove dummy, add real variant based on weight matching)
- Same button visibility conditions

The modules can coexist but should not be used together on the same products.

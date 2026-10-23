# Livestock Weight-Based Receiving - Complete Setup Guide

## 📋 Prerequisites

1. **Odoo Version**: 15.0 or higher
2. **Required Modules**: 
   - Base
   - Product
   - Stock/Inventory
   - Purchase
3. **User Access Rights**: Stock Manager + Purchase Manager

---

## 🚀 Installation Steps

### Step 1: Install the Module

1. Navigate to **Apps** menu
2. Click **Update Apps List** (may require developer mode)
3. Search for "Inventory Customization"
4. Click **Install**
5. Wait for installation to complete

**✅ Verification**: Module should appear in installed apps list

---

## 📝 Configuration Steps

### Step 2: Configure Livestock Variants

**Demo data automatically creates:**
- Sadqa
- Aqiqa
- Qurbani

**To add more variants manually:**

1. Go to **Inventory > Configuration > Livestock Variants**
2. Click **Create**
3. Enter Name (e.g., "Qurbani", "Sadqa", "Aqiqa")
4. Click **Save**

**✅ Created**: 3+ livestock variant types

---

### Step 3: Configure Product Attributes with Weight Ranges

**Demo data automatically creates** a "Weight Range" attribute with values:
- Small (10-20 kg)
- Medium (20-30 kg)
- Large (30-50 kg)
- Extra Large (50-100 kg)

**To verify or customize:**

1. Go to **Sales > Configuration > Settings**
2. Enable **Variants** (Product Variants feature)
3. Go to **Sales > Configuration > Product Attributes**
4. Find/Edit "Weight Range" attribute
5. Click on **Values** smart button
6. For each value, set:
   - **Name**: e.g., "Small (10-20 kg)"
   - **From (kg)**: 10
   - **To (kg)**: 20
7. Click **Save**

**✅ Configured**: Attribute with 4+ weight range values

---

### Step 4: Create Purchase Product (Dummy Product)

This is the product you'll use in Purchase Orders.

1. Go to **Purchase > Products > Products**
2. Click **Create**
3. Fill in:
   - **Product Name**: "Goat - Purchase"
   - **Product Type**: Storable Product
   - **Can be Purchased**: ✓ (checked)
   - **Can be Sold**: ☐ (optional)
   - **Cost**: 150.00 (base price per unit)
4. Scroll to **Options** section:
   - **Is Receive By Weight**: ✓ (optional, legacy field)
   - **Is Livestock Product**: ✓ (checked) ← IMPORTANT!
5. Click **Save**

**✅ Created**: 1 purchase product marked as livestock

---

### Step 5: Create Real Livestock Products with Variants

These are the actual products that will appear in inventory after receiving.

#### 5.1 Create Product Template

1. Go to **Inventory > Products > Products**
2. Click **Create**
3. Fill in:
   - **Product Name**: "Goat - Sadqa"
   - **Product Type**: Storable Product
   - **Can be Purchased**: ☐ (unchecked)
   - **Can be Sold**: ✓ (checked, if you sell them)

#### 5.2 Configure Livestock Settings

4. Scroll to **Options** section:
   - **Is Livestock Product**: ✓ (checked)
5. The **Livestock Configuration** section appears below:
   - **Livestock Variant**: Select "Sadqa"
   - **Purchase Product**: Select "Goat - Purchase"
   - **Main Attribute**: Select "Weight Range"

#### 5.3 Add Attributes to Create Variants

6. Go to **Attributes & Variants** tab
7. Click **Add a line**
8. Select **Attribute**: "Weight Range"
9. Select **Values**: Check all (Small, Medium, Large, Extra Large)
10. Click **Save**

**Result**: System auto-creates 4 product variants:
- Goat - Sadqa (Small)
- Goat - Sadqa (Medium)
- Goat - Sadqa (Large)
- Goat - Sadqa (Extra Large)

#### 5.4 Repeat for Other Livestock Variants

Create similar products for:
- "Goat - Aqiqa" (linked to Aqiqa variant)
- "Goat - Qurbani" (linked to Qurbani variant)
- etc.

Each will create its own 4 variants based on weight ranges.

**✅ Created**: 3 product templates × 4 variants = 12 product variants

---

## 🧪 Testing the Complete Flow

### Test 1: Create Purchase Order

1. Go to **Purchase > Orders > Create**
2. Select a **Vendor**
3. Add Order Line:
   - **Product**: "Goat - Purchase"
   - **Quantity**: 5
   - **Notice**: Price auto-multiplies by max weight (to_kg = 100)
4. Click **Confirm Order**

**✅ Expected**: 
- Order confirmed
- Price = base price × 100 (if max to_kg = 100)

---

### Test 2: Receive Products

1. From Purchase Order, click **Receipt** smart button
2. Or go to **Inventory > Operations > Receipts**
3. Find your receipt
4. Click **Validate** button
5. Transfer state changes to **Done**

**✅ Expected**: Receipt validated with 5 units

---

### Test 3: Open Receive by Weight Wizard

1. After validation, look in **header** area
2. Click **"Receive by Weight"** button
   - **Note**: Only appears for livestock products (check_stock=True)

**✅ Expected**: Wizard opens with 5 pre-filled lines

---

### Test 4: Enter Weights and Variants

The wizard shows a table with 5 rows (one per goat):

| S.No | Product | Livestock Variant | Weight (kg) |
|------|---------|-------------------|-------------|
| 1 | Goat - Purchase | [Select] | [Enter] |
| 2 | Goat - Purchase | [Select] | [Enter] |
| 3 | Goat - Purchase | [Select] | [Enter] |
| 4 | Goat - Purchase | [Select] | [Enter] |
| 5 | Goat - Purchase | [Select] | [Enter] |

**Fill in data:**
```
Line 1: Variant = Sadqa,   Weight = 15
Line 2: Variant = Sadqa,   Weight = 25
Line 3: Variant = Aqiqa,   Weight = 35
Line 4: Variant = Qurbani, Weight = 45
Line 5: Variant = Sadqa,   Weight = 22
```

**Watch the totals update:**
- **Total Weight**: 142 kg
- **Bill Amount**: Auto-calculated based on product price × weight

**✅ Expected**: All fields editable, totals updating

---

### Test 5: Save (Optional)

1. Click **"Save"** button
2. Close the wizard
3. Re-open: Click **"Receive by Weight"** again
4. Previously entered data is preserved!

**✅ Expected**: Can save and resume later

---

### Test 6: Receive Products

1. Verify all weights and variants are correct
2. Click **"Receive"** button
3. Wait for processing...

**What happens internally:**
```
1. Remove 5 units of "Goat - Purchase" from stock
2. Process each line:
   - Line 1 (15kg, Sadqa) → Finds "Goat - Sadqa (Small)" → Add 1 unit
   - Line 2 (25kg, Sadqa) → Finds "Goat - Sadqa (Medium)" → Add 1 unit
   - Line 3 (35kg, Aqiqa) → Finds "Goat - Aqiqa (Large)" → Add 1 unit
   - Line 4 (45kg, Qurbani) → Finds "Goat - Qurbani (Large)" → Add 1 unit
   - Line 5 (22kg, Sadqa) → Finds "Goat - Sadqa (Medium)" → Add 1 unit
3. Save bill_amount to stock picking
4. Update PO line price with actual cost
```

**✅ Expected**: Processing completes successfully

---

### Test 7: Verify Stock Quantities

1. Go to **Inventory > Products > Products**

**Check each variant:**

**"Goat - Purchase"**
- On Hand: 0 (removed)

**"Goat - Sadqa (Small)"**
- On Hand: 1 (from 15kg goat)

**"Goat - Sadqa (Medium)"**
- On Hand: 2 (from 25kg + 22kg goats)

**"Goat - Aqiqa (Large)"**
- On Hand: 1 (from 35kg goat)

**"Goat - Qurbani (Large)"**
- On Hand: 1 (from 45kg goat)

**✅ Expected**: Correct quantities in appropriate variants

---

### Test 8: Check Stock Picking Bill Amount

1. Go back to **Stock Picking** (Receipt)
2. Look for **"Bill Amount"** field (below Origin)
3. Should show total calculated bill: 142 × price

**✅ Expected**: Bill amount displayed correctly

---

### Test 9: Verify Purchase Order Price Update

1. Go back to **Purchase Order**
2. Check order line
3. **Unit Price** should be updated to: bill_amount ÷ 5
4. This reflects actual weighted cost per unit

**✅ Expected**: PO line price reflects weighted pricing

---

### Test 10: Create Vendor Bill

1. From Purchase Order, click **"Create Bill"**
2. Bill is created with updated pricing
3. Can adjust if needed
4. Click **Confirm**

**✅ Expected**: Bill uses weighted unit price

---

## 🔍 Troubleshooting Common Issues

### Issue: "Receive by Weight" button not showing

**Cause**: Product not marked as livestock
**Solution**: 
1. Edit product template
2. Check "Is Livestock Product"
3. Save

---

### Issue: "No product template found" error

**Cause**: Missing product configuration
**Check:**
- Real variant has `purchase_product` = dummy product ✓
- Real variant has `livestock_variant` = selected type ✓
- Real variant has attributes configured ✓

---

### Issue: "No matching variant found in range X kg"

**Cause**: Weight doesn't match any range
**Check:**
- Weight 15kg → Needs range 10-20 ✓
- Weight 5kg → No range covers it ✗

**Solution**: 
- Adjust weight entry, or
- Add more attribute values with wider ranges

---

### Issue: Cannot save wizard data

**Cause**: Missing access rights
**Solution**: Check security/ir.model.access.csv has livestock_variant entry

---

### Issue: Price not calculating correctly

**Cause**: Main attribute not set
**Solution**: 
1. Edit product template
2. Set **Main Attribute** = "Weight Range"
3. Ensure attribute values have to_kg filled

---

## 📊 Sample Data Summary

After demo data installation, you have:

- **3 Livestock Variants**: Sadqa, Aqiqa, Qurbani
- **1 Attribute**: Weight Range
- **4 Attribute Values**: Small (10-20), Medium (20-30), Large (30-50), XL (50-100)

You still need to create:
- **Purchase products** (dummy products for PO)
- **Real variant products** (actual inventory items)

---

## 🎯 Quick Start Checklist

- [ ] Module installed
- [ ] Livestock variants exist (3+)
- [ ] Weight Range attribute configured (4+ values)
- [ ] Purchase product created (1+ with check_stock=True)
- [ ] Real variant products created (3+ with attributes)
- [ ] Purchase order created and confirmed
- [ ] Receipt validated
- [ ] Receive by Weight wizard tested
- [ ] Stock quantities verified
- [ ] Bill amount checked
- [ ] Vendor bill created

---

## 📞 Support

If issues persist:
1. Enable Developer Mode
2. Check server logs for errors
3. Verify all fields are properly configured
4. Test with demo data first before real data

**Complete setup time**: ~15-20 minutes
**First test workflow**: ~5 minutes

Good luck! 🎉

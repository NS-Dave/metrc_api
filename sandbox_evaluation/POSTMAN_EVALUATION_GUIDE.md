# Metrc API Evaluation - Postman Guide

## Your Credentials

Based on your screenshot:
- **Vendor Key**: `5ZHpEC3fDQ9ISCj-5W4aUeKZMLAR40TCtgbJkkmP564d-Dgk`
- **User Key**: `Tm1GKLyHeJwsIqMFrh0c5K25oxmZp-iuZclt0xVqKKo8ZgAq`

## Step 1: Set Up Postman Environment

1. **Open Postman** and go to the Metrc API collection you imported

2. **Edit Collection Variables**:
   - Click on the collection → Variables tab
   - Set these values:

```
Metrc.api.server = https://sandbox-api-ma.metrc.com
Metrc.vendorKey = 5ZHpEC3fDQ9ISCj-5W4aUeKZMLAR40TCtgbJkkmP564d-Dgk
Metrc.userKey = Tm1GKLyHeJwsIqMFrh0c5K25oxmZp-iuZclt0xVqKKo8ZgAq
```

3. **Check Collection Auth**:
   - Go to Authorization tab
   - Should already be set to "Basic Auth"
   - Username: `{{Metrc.vendorKey}}`
   - Password: `{{Metrc.userKey}}`

## Step 2: Generate Sandbox License (IMPORTANT!)

Before you can do any evaluation tasks, you need to generate a sandbox facility. This is mentioned in the email.

### Use: `POST /sandbox/v2/integrator/setup`

1. **Find this request** in the Postman collection under: `v2 → Sandbox → POST Integrator Setup`

2. **Request Body** (example):
```json
{
  "CompanyName": "NS Evaluation Test",
  "LicenseType": "Cultivation",
  "State": "MA"
}
```

3. **Send the request** and save the response

4. **Extract from response**:
   - License Number (e.g., `CML17-0000001`)
   - Facility details
   - Available tags

5. **Add License Number to Postman variables**:
   - `licenseNumber = [YOUR_LICENSE_NUMBER]`

> **Note**: You may need to create both a Cultivation and Processing facility if testing both license types.

## Step 3: Complete Evaluation Tasks

Now you can work through each section of the evaluation. Here's the workflow for each task:

---

### TASK TEMPLATE

For each task you complete in Postman, capture these items:

✅ **Result Code**: (from Postman response - should be 200)  
✅ **License Facility**: (your license number)  
✅ **ID Number**: (from GET response after creating)  
✅ **Name/Tag Created**: (the name or tag you created)  
✅ **Last Modified Date**: (from GET response or current date)  
✅ **Request Sent**: (copy URL from Postman)  
✅ **JSON Body/Response**: (copy and minify using https://jsonformatter.org/minify)

---

## LOCATIONS Section

### Step 1: Create Location
**Endpoint**: `POST /locations/v2/create`

**Query Param**: 
- `licenseNumber = {{licenseNumber}}`

**Request Body**:
```json
[
  {
    "Name": "Eval Location 001",
    "LocationTypeName": "Default"
  }
]
```

**After sending**:
1. Verify 200 response
2. Note the request URL
3. Minify the request body

### Step 2: Get Location ID
**Endpoint**: `GET /locations/v2/active`

**Query Param**:
- `licenseNumber = {{licenseNumber}}`

**From response**:
- Find your "Eval Location 001"
- Copy the `Id` value (e.g., 12345)

### Step 3: Update Location
**Endpoint**: `PUT /locations/v2/update`

**Request Body**:
```json
[
  {
    "Id": 12345,
    "Name": "Eval Location 001 Updated",
    "LocationTypeName": "Default"
  }
]
```

### Step 4: GET by ID
**Endpoint**: `GET /locations/v2/{id}`

**Path variable**: Replace `{id}` with your location ID

**Record in CSV**:
- Result code: 200
- License Facility: [your license]
- ID Number: 12345
- Location Name: "Eval Location 001 Updated"
- Request Sent: `https://sandbox-api-ma.metrc.com/locations/v2/create?licenseNumber=XXX`
- JSON Body: `[{"Name":"Eval Location 001","LocationTypeName":"Default"}]`

---

## STRAINS Section

### Step 1: Create Strain
**Endpoint**: `POST /strains/v2/create`

**Request Body**:
```json
[
  {
    "Name": "Eval Strain 001",
    "TestingStatus": "None",
    "ThcLevel": 0.18,
    "CbdLevel": 0.02,
    "IndicaPercentage": 50.0,
    "SativaPercentage": 50.0
  }
]
```

### Step 2: Get Strain ID
**Endpoint**: `GET /strains/v2/active`

Find your strain and copy the ID.

### Step 3: Update Strain
**Endpoint**: `PUT /strains/v2/update`

**Request Body**:
```json
[
  {
    "Id": [STRAIN_ID],
    "Name": "Eval Strain 001",
    "TestingStatus": "None",
    "ThcLevel": 0.20,
    "CbdLevel": 0.03,
    "IndicaPercentage": 60.0,
    "SativaPercentage": 40.0
  }
]
```

### Step 4: GET by ID
**Endpoint**: `GET /strains/v2/{id}`

**Record all validation items in Strains.csv**

---

## ITEMS Section

### Step 1: Create Item
**Endpoint**: `POST /items/v2/create`

**Request Body**:
```json
[
  {
    "ItemCategory": "Buds",
    "Name": "Eval Item 001",
    "UnitOfMeasure": "Grams",
    "Strain": "Eval Strain 001",
    "UnitThcPercent": 18.5,
    "UnitCbdPercent": 2.0
  }
]
```

### Step 2: Get Item ID
**Endpoint**: `GET /items/v2/active`

### Step 3: Update Item (change UOM)
**Endpoint**: `PUT /items/v2/update`

**Request Body**:
```json
[
  {
    "Id": [ITEM_ID],
    "ItemCategory": "Buds",
    "Name": "Eval Item 001",
    "UnitOfMeasure": "Ounces",
    "Strain": "Eval Strain 001",
    "UnitThcPercent": 18.5,
    "UnitCbdPercent": 2.0
  }
]
```

### Step 4: GET by ID
**Endpoint**: `GET /items/v2/{id}`

**Record all validation items in Items.csv**

---

## PLANT BATCHES Section

> **Important**: Plant Batches are UNTRACKED plants. You don't need individual plant tags for this section. Plant tags are only needed for the separate "Plants" section.

### Step 1: Create Plant Batch (6 plants)
**Endpoint**: `POST /plantbatches/v2/createplantings`

**Request Body**:
```json
[
  {
    "Name": "Eval Batch 001",
    "Type": "Seed",
    "Count": 6,
    "Strain": "Eval Strain 001",
    "Location": "Eval Location 001 Updated",
    "PatientLicenseNumber": null,
    "ActualDate": "2025-12-19"
  }
]
```

**After sending**:
- Record the response and request URL
- Use `GET /plantbatches/v2/{id}` to get the Plant Batch ID
- Note: `UntrackedCount` should be 6

### Step 2: Create Package from Batch (3 clones)
**Endpoint**: `POST /plantbatches/v2/packages?licenseNumber={{licenseNumber}}`

**Get available package tag first**: `GET /plantbatches/v2/availabletags?licenseNumber={{licenseNumber}}`
- Look for a tag with `TagInventoryTypeName: "CannabisPackage"`

**Request Body**:
```json
[
  {
    "PlantBatchId": [BATCH_ID_FROM_STEP_1],
    "PlantBatchName": "Eval Batch 001",
    "Count": 3,
    "LocationId": [YOUR_LOCATION_ID],
    "ItemId": null,
    "Tag": "[PACKAGE_TAG]",
    "PatientLicenseNumber": null,
    "Note": null,
    "IsTradeSample": false,
    "IsDonation": false,
    "ActualDate": "2025-12-19"
  }
]
```

**After sending**:
- This removes 3 plants from the batch (6 - 3 = 3 remaining)
- `UntrackedCount` should now be 3

### Step 3: Change Growth Phase (remaining plants)
**Endpoint**: `POST /plantbatches/v2/growthphase?licenseNumber={{licenseNumber}}`

**Request Body**:
```json
[
  {
    "PlantBatchId": [BATCH_ID_FROM_STEP_1],
    "PlantBatchName": "Eval Batch 001",
    "GrowthPhase": "Vegetative",
    "GrowthDate": "2025-12-19"
  }
]
```

### Step 4: Destroy 1 Plant from Batch
**Endpoint**: `DELETE /plantbatches/v2?licenseNumber={{licenseNumber}}`

**Request Body**:
```json
[
  {
    "PlantBatchId": [BATCH_ID_FROM_STEP_1],
    "PlantBatchName": "Eval Batch 001",
    "Count": 1,
    "ReasonNote": "Evaluation test - plant destruction",
    "ActualDate": "2025-12-19"
  }
]
```

**After sending**:
- This removes 1 plant (3 - 1 = 2 remaining)
- `UntrackedCount` should now be 2

**Record all validation items in PlantBatches.csv**

---

## PLANTS Section

> **Note**: This section requires working with existing plants in the sandbox. You may need to first move some plant batches to flowering stage.

### Get Flowering Plants First
**Endpoint**: `GET /plants/v2/flowering`

Pick one plant to use for the tasks below.

### Step 1: Move Plant to Different Location
**Endpoint**: `PUT /plants/v2/moveplants`

**Request Body**:
```json
[
  {
    "Id": null,
    "Label": "[PLANT_TAG]",
    "Location": "Eval Location 001 Updated",
    "ActualDate": "2025-12-18"
  }
]
```

### Step 2: Create Immature Plant Batch
**Endpoint**: `POST /plants/v2/plantings`

### Step 3: Create Package of Seeds/Clones
**Endpoint**: `POST /plants/v2/plantbatch/packages`

### Step 4: Destroy Plant
**Endpoint**: `DELETE /plants/v2`

### Step 5: Manicure Plant
**Endpoint**: `POST /plants/v2/manicureplants`

### Step 6: Harvest Plants
**Endpoint**: `PUT /plants/v2/harvestplants`

**Request Body Example**:
```json
[
  {
    "Plant": "[PLANT_TAG]",
    "Weight": 100.5,
    "UnitOfWeight": "Grams",
    "DryingLocation": "Eval Location 001 Updated",
    "HarvestName": "Eval Harvest 001",
    "PatientLicenseNumber": null,
    "ActualDate": "2025-12-18"
  }
]
```

**Record all validation items in Plants.csv**

---

## HARVESTS Section

### Step 1: Create Package from Harvest
**Endpoint**: `POST /harvests/v2/create/packages`

**Get available tag first**: `GET /packages/v2/available`

**Request Body**:
```json
[
  {
    "Tag": "[AVAILABLE_TAG]",
    "Location": "Eval Location 001 Updated",
    "Item": "Eval Item 001",
    "UnitOfWeight": "Grams",
    "PatientLicenseNumber": null,
    "Note": null,
    "IsProductionBatch": false,
    "ProductionBatchNumber": null,
    "IsTradeSample": false,
    "IsTestingSample": false,
    "ProductRequiresRemediation": false,
    "ActualDate": "2025-12-18",
    "Ingredients": [
      {
        "HarvestId": null,
        "HarvestName": "Eval Harvest 001",
        "Weight": 50.0,
        "UnitOfWeight": "Grams"
      }
    ]
  }
]
```

### Step 2: Remove Waste from Harvest
**Endpoint**: `POST /harvests/v2/removewaste`

**Request Body**:
```json
[
  {
    "Id": null,
    "HarvestName": "Eval Harvest 001",
    "UnitOfWeight": "Grams",
    "WasteWeight": 10.0,
    "WasteType": "Plant Material",
    "WasteReasonName": "Other",
    "ReasonNote": "Evaluation test waste",
    "ActualDate": "2025-12-18"
  }
]
```

### Step 3: Finish Harvest
**Endpoint**: `PUT /harvests/v2/finish`

### Step 4: Unfinish Harvest
**Endpoint**: `PUT /harvests/v2/unfinish`

**Record all validation items in Harvest.csv**

---

## PACKAGES Section

### Step 1: Create Package from Package
**Endpoint**: `POST /packages/v2/create`

**Get source package and new tag**

**Request Body**:
```json
[
  {
    "Tag": "[NEW_TAG]",
    "Location": "Eval Location 001 Updated",
    "Item": "Eval Item 001",
    "Quantity": 10.0,
    "UnitOfMeasure": "Grams",
    "PatientLicenseNumber": null,
    "Note": null,
    "IsProductionBatch": false,
    "ProductionBatchNumber": null,
    "IsTradeSample": false,
    "IsTestingSample": false,
    "ProductRequiresRemediation": false,
    "ActualDate": "2025-12-18",
    "Ingredients": [
      {
        "Package": "[SOURCE_PACKAGE_TAG]",
        "Quantity": 10.0,
        "UnitOfMeasure": "Grams"
      }
    ]
  }
]
```

### Step 2: Change Item
**Endpoint**: `PUT /packages/v2/change/item`

### Step 3: Adjust Quantity to 0
**Endpoint**: `PUT /packages/v2/adjust`

**Request Body**:
```json
[
  {
    "Label": "[PACKAGE_TAG]",
    "Quantity": -10.0,
    "UnitOfMeasure": "Grams",
    "AdjustmentReason": "Waste",
    "AdjustmentDate": "2025-12-18",
    "ReasonNote": "Evaluation test adjustment"
  }
]
```

### Step 4: Finish Package
**Endpoint**: `PUT /packages/v2/finish`

### Step 5: Unfinish Package
**Endpoint**: `PUT /packages/v2/unfinish`

**Record all validation items in Packages.csv**

---

## Tips for Success

### Getting Available Tags
You'll frequently need tags. Use these endpoints:
- **Plant tags**: `GET /plants/v2/additives/types` or check plant batch creation responses
- **Package tags**: `GET /packages/v2/available`

### Checking Your Work
After each POST/PUT operation:
1. Verify 200 response
2. Do a GET to find the ID
3. GET by ID to verify the change
4. Copy the LastModified date

### Minifying JSON
Use: https://jsonformatter.org/minify
- Paste your JSON
- Click "Minify"
- Copy result into CSV cell

### Common Issues

**401 Unauthorized**
- Check your vendor key and user key are correct in variables
- Ensure Basic Auth is enabled on collection

**404 Not Found**
- Make sure you included `?licenseNumber={{licenseNumber}}` in URL
- Verify the license number variable is set

**400 Bad Request**
- Check your JSON syntax
- Verify all required fields are present
- Ensure dates are in YYYY-MM-DD format
- Check that referenced items (strains, locations) exist

**Resource not found errors**
- You may need to create dependencies first (strains before items, items before packages)
- Double-check exact names (they're case-insensitive but must match)

### Recording Results

For each CSV file, you need to record:

| Column | What to Record |
|--------|---------------|
| Result code | Should always be 200 |
| License Facility | Your sandbox license number |
| ID Number | The ID from GET response (5-digit number) |
| Name/Tag Created | Exact name or tag you created |
| Last Modified Date | From GET response or current date/time |
| Request Sent | Full URL with query params |
| JSON Body/Response | Minified JSON of request or response |

## Workflow Summary

1. ✅ Set up Postman with your credentials
2. ✅ Generate sandbox facility using POST /sandbox/v2/integrator/setup
3. ✅ Complete Locations tasks → record in CSV
4. ✅ Complete Strains tasks → record in CSV
5. ✅ Complete Items tasks → record in CSV
6. ✅ Complete Plant Batches tasks → record in CSV
7. ✅ Complete Plants tasks → record in CSV
8. ✅ Complete Harvests tasks → record in CSV
9. ✅ Complete Packages tasks → record in CSV
10. ✅ Fill out CompanyInformation.csv
11. ✅ Mark permissions in Permissions.csv
12. ✅ Submit all CSVs to api-info@metrc.com

Good luck with your evaluation!

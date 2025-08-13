# Google Sheets API Setup Guide

## Prerequisites
1. Install required packages:
```bash
pip install -r sheets_requirements.txt
```

## Option 1: Service Account (Recommended for Automation)

### Step 1: Create Google Cloud Project
1. Go to https://console.cloud.google.com/
2. Create a new project or select existing one
3. Enable Google Sheets API and Google Drive API

### Step 2: Create Service Account
1. Go to IAM & Admin > Service Accounts
2. Click "Create Service Account"
3. Enter name: "foreclosure-sheet-exporter"
4. Click "Create and Continue"
5. Skip role assignment (click "Continue")
6. Click "Done"

### Step 3: Generate Service Account Key
1. Click on the created service account
2. Go to "Keys" tab
3. Click "Add Key" > "Create new key"
4. Select "JSON" format
5. Download the JSON file
6. Rename it to `service_account.json`
7. Place it in the same directory as `foreclosure_sheet_exporter.py`

### Step 4: Share Spreadsheet with Service Account
1. Open your Google Sheets spreadsheet
2. Click "Share" button
3. Add the service account email (found in the JSON file)
4. Give "Editor" permissions
5. Click "Send"

## Option 2: OAuth2 (Interactive Setup)

### Step 1: Create OAuth2 Credentials
1. Go to Google Cloud Console
2. Go to APIs & Services > Credentials
3. Click "Create Credentials" > "OAuth client ID"
4. Select "Desktop application"
5. Enter name: "foreclosure-exporter"
6. Download the JSON file
7. Rename it to `credentials.json`
8. Place it in the same directory as `foreclosure_sheet_exporter.py`

### Step 2: First Run
1. Run the script for the first time
2. It will open a browser window for authentication
3. Sign in with your Google account
4. Grant permissions
5. The script will save a `token.json` file for future runs

## Running the Exporter

```bash
python foreclosure_sheet_exporter.py
```

The script will:
1. Connect to Google Sheets
2. Scan all case folders for data
3. Export new cases to the spreadsheet
4. Monitor for new cases every 30 minutes
5. Keep the spreadsheet updated automatically

## Spreadsheet Features

- **Headers**: Automatically sets up proper column headers
- **Sorting**: New cases appear at the top
- **Formatting**: Professional appearance with colors and alignment
- **Attorney Websites**: Automatically extracts domains from email addresses
- **Incremental Updates**: Only adds new cases, doesn't duplicate existing ones
- **Comprehensive Data**: All important case information in organized columns

## Important Notes

- The spreadsheet will be formatted automatically
- New cases always appear at the top (newest first)
- Attorney email domains are converted to website URLs
- All financial amounts are properly formatted as currency
- The script runs continuously and monitors for new cases
- Previous exports are tracked to avoid duplicates

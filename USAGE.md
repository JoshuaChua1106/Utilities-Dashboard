# Usage Guide - Utilities Tracker

## Local Development Usage

### Initial Setup

1. **Environment Setup**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Database Initialization**:
   ```bash
   python local_dev/init_db.py
   ```

3. **Configure Providers** (`config/providers.json`):
   ```json
   {
     "EnergyAustralia": {
       "email": "noreply@energyaustralia.com.au",
       "service_type": "Electricity",
       "subject_keywords": ["bill", "invoice", "statement"],
       "date_range_days": 90,
       "attachment_types": [".pdf"]
     },
     "GasWorks": {
       "email": "billing@gasworks.com",
       "service_type": "Gas", 
       "subject_keywords": ["gas bill", "invoice"],
       "date_range_days": 90,
       "attachment_types": [".pdf"]
     }
   }
   ```

4. **Set OAuth Credentials** (`config/credentials.json`):
   ```json
   {
     "gmail": {
       "client_id": "your-gmail-client-id",
       "client_secret": "your-gmail-client-secret",
       "refresh_token": "your-refresh-token"
     }
   }
   ```

### Running the Local Pipeline

#### 1. Fetch Invoices from Email
```bash
# Initial historical scrape
python email_fetcher/fetch_invoices.py --mode=historical

# Incremental updates (only new invoices)
python email_fetcher/fetch_invoices.py --mode=incremental
```

#### 2. Parse PDF Invoices
```bash
# Parse all unprocessed PDFs
python pdf_parser/parse_pdfs.py

# Parse specific provider
python pdf_parser/parse_pdfs.py --provider=EnergyAustralia

# Reprocess with new template
python pdf_parser/parse_pdfs.py --reprocess
```

#### 3. Start Web Application
```bash
# Start backend API
python web_app/backend/app.py

# In separate terminal, start frontend
cd web_app/frontend
npm start
```

**Access Points:**
- Web App: `http://localhost:3000`
- API: `http://localhost:5000/api`
- Power BI Data: `./data/invoices.csv`

### Data Access Methods

#### Power BI Dashboard (Local)
1. Open Power BI Desktop
2. Get Data → Text/CSV
3. Select `./data/invoices.csv`
4. Load data and refresh as needed
5. Use provided `.pbix` template from `powerbi_dashboard/`

#### Web Application Features
- **Service Filtering**: Toggle between Electricity, Gas, Water
- **Time Periods**: Monthly, bi-monthly, quarterly views
- **Interactive Charts**: Line charts (trends), bar charts (usage comparison)
- **Data Tables**: Sortable and filterable invoice details
- **Manual Sync**: Button to trigger immediate invoice fetch
- **Export**: Download filtered data as CSV

#### Direct Database Access
```bash
# SQLite CLI
sqlite3 ./data/invoices.db

# View tables
.tables

# Query invoices
SELECT provider_name, service_type, total_amount, invoice_date 
FROM invoices 
ORDER BY invoice_date DESC 
LIMIT 10;
```

### Environment Variables (Local Development)

Create `.env` file in project root:
```bash
# Environment Mode
ENVIRONMENT=local
AWS_MODE=false

# Database Configuration
DATABASE_TYPE=sqlite
DATABASE_PATH=./data/invoices.db

# Storage Configuration  
STORAGE_TYPE=filesystem
STORAGE_BASE_PATH=./data/invoices/

# OCR Configuration
OCR_TYPE=local
OCR_ENGINES=pdfplumber,pytesseract

# API Configuration
API_HOST=localhost
API_PORT=5000
WEB_HOST=localhost
WEB_PORT=3000

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/utilities-tracker.log
```

## AWS Production Usage

**⚠️ AWS deployment should only be performed after local testing is complete and explicit approval is given.**

### AWS Environment Setup

1. **Deploy Infrastructure**:
   ```bash
   cd infrastructure/
   npm install
   cdk bootstrap
   cdk deploy --all
   ```

2. **Configure AWS Services**:
   ```bash
   python aws_setup/configure_services.py
   python aws_setup/upload_configs.py
   ```

3. **Migrate Local Data**:
   ```bash
   python aws_setup/migrate_data.py --from-local
   ```

4. **Switch to AWS Mode**:
   ```bash
   export AWS_MODE=true
   export ENVIRONMENT=production
   ```

### AWS Pipeline Usage

#### Scheduled Invoice Processing
- **EventBridge**: Triggers Lambda functions weekly
- **Manual Trigger**: 
  ```bash
  aws lambda invoke --function-name utilities-email-fetcher response.json
  ```

#### Web Application Access
- **Production URL**: `https://utilities.yourdomain.com`
- **API Gateway**: `https://api.utilities.yourdomain.com`

#### Power BI Integration (AWS)
1. **S3 Connector**: Connect Power BI to S3 bucket
2. **Automated CSV**: Lambda exports to S3 on schedule
3. **Refresh Schedule**: Configure Power BI Service refresh

### Monitoring & Troubleshooting

#### Local Development
```bash
# Check logs
tail -f ./logs/utilities-tracker.log

# Database status
python local_dev/check_db_status.py

# Test email connection
python email_fetcher/test_connection.py
```

#### AWS Production
```bash
# CloudWatch logs
aws logs tail /aws/lambda/utilities-email-fetcher --follow

# Check function status  
aws lambda get-function --function-name utilities-email-fetcher

# RDS connection test
python aws_setup/test_rds_connection.py
```

## Common Workflows

### Adding a New Provider
1. **Update Provider Config**:
   ```json
   {
     "NewUtilityCo": {
       "email": "billing@newutilityco.com",
       "service_type": "Electricity",
       "subject_keywords": ["bill", "invoice"],
       "date_range_days": 90,
       "attachment_types": [".pdf"]
     }
   }
   ```

2. **Create Parsing Template** (`config/templates/new_utility_co.json`):
   ```json
   {
     "provider": "NewUtilityCo",
     "service_type": "Electricity",
     "patterns": {
       "invoice_date": "Date:\\s*(\\d{1,2}/\\d{1,2}/\\d{4})",
       "total_amount": "Total:\\s*\\$([\\d,]+\\.\\d{2})",
       "usage_quantity": "Usage:\\s*([\\d,]+)\\s*kWh"
     }
   }
   ```

3. **Test Parsing**:
   ```bash
   python pdf_parser/test_template.py --provider=NewUtilityCo --pdf=test_invoice.pdf
   ```

### Data Export and Backup
```bash
# Export to CSV
python data_storage/export_csv.py --output=./exports/invoices_backup.csv

# Database backup
python local_dev/backup_db.py --output=./backups/

# S3 sync (AWS mode)
python aws_setup/sync_to_s3.py
```

### Performance Optimization
```bash
# Rebuild database indexes
python data_storage/optimize_db.py

# Clean up old processed files
python local_dev/cleanup_old_files.py --days=365

# Validate data integrity
python data_storage/validate_data.py
```

## Troubleshooting

### Common Issues

1. **Email API Authentication Errors**:
   ```bash
   python email_fetcher/refresh_oauth.py
   ```

2. **PDF Parsing Failures**:
   ```bash
   python pdf_parser/debug_pdf.py --pdf=problematic_invoice.pdf
   ```

3. **Database Connection Issues**:
   ```bash
   python local_dev/reset_db.py  # Local only
   ```

4. **Missing Dependencies**:
   ```bash
   pip install -r requirements.txt --upgrade
   ```

### Support and Maintenance

- **Log Files**: Check `./logs/` directory for detailed error information
- **Test Suite**: Run `python -m pytest tests/` for comprehensive validation
- **Data Validation**: Use `python data_storage/validate_data.py` to check integrity
- **Performance Metrics**: Monitor via web app's `/api/health` endpoint
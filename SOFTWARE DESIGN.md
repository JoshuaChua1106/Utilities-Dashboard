# Software Design - Utilities Tracker

## Architecture Philosophy: Local-First, AWS-Ready

The system is designed with a **dual-environment architecture** that prioritizes local development while maintaining AWS production readiness through abstraction layers and configuration-driven deployment.

## Core Architecture Principles

### 1. Environment Abstraction
- **Storage Adapter Pattern**: Single interface for local filesystem and S3
- **Database Adapter Pattern**: Unified access to SQLite and PostgreSQL RDS  
- **OCR Adapter Pattern**: Seamless switching between local OCR and AWS Textract
- **Configuration-Driven**: Environment switching via env vars, not code changes

### 2. Service Separation
Each service operates independently with clear interfaces:
- **Email Fetcher**: OAuth2 email integration with configurable storage
- **PDF Parser**: Document processing with provider-specific templates
- **Data Storage**: Unified data layer with dual output (CSV + Database)
- **Web Application**: Analytics interface with responsive design
- **Power BI Integration**: Automated data export pipeline

## Service Design Details

### Email Fetcher Service

**Local Implementation:**
```python
class EmailFetcher:
    def __init__(self):
        self.storage = StorageAdapter()  # Auto-detects local vs S3
        self.credentials = CredentialManager()  # Local JSON vs Secrets Manager
        
    def fetch_invoices(self):
        # OAuth2 connection (same for both environments)
        # Search emails by provider config
        # Download PDFs to configured storage backend
```

**Responsibilities:**
- OAuth2 authentication with Gmail/Outlook APIs
- Email search using provider-specific criteria from config
- PDF attachment download with organized storage structure  
- Processing history tracking to avoid duplicates
- Comprehensive logging with CloudWatch-compatible format

**Local Storage Structure:**
```
./data/
├── invoices/
│   ├── energy-australia/
│   ├── gas-works/
│   └── water-corp/
├── processed/
└── logs/
```

**AWS Storage Structure:**
```
s3://utilities-bucket/
├── invoices/energy-australia/
├── invoices/gas-works/
├── invoices/water-corp/
├── processed/
└── logs/
```

### PDF Parser Service

**Local Implementation:**
```python
class PDFParser:
    def __init__(self):
        self.ocr = OCRAdapter()  # pdfplumber/pytesseract vs Textract
        self.templates = TemplateManager()  # JSON files vs Parameter Store
        
    def parse_pdf(self, pdf_path):
        # Extract text using appropriate OCR backend
        # Apply provider-specific parsing template
        # Validate and structure data
        # Return standardized invoice object
```

**Responsibilities:**
- Text extraction using local OCR (pdfplumber, pytesseract) or AWS Textract
- Provider-specific parsing using JSON templates
- Data validation and error handling with retry logic
- Structured data output with standardized schema

**Data Extraction Schema:**
```python
@dataclass
class Invoice:
    id: str
    provider_name: str
    service_type: str  # Electricity, Gas, Water
    invoice_date: datetime
    total_amount: Decimal
    usage_quantity: Decimal
    usage_rate: Decimal
    service_charge: Decimal
    billing_period_start: datetime
    billing_period_end: datetime
    file_path: str
    processing_status: str
    created_at: datetime
    updated_at: datetime
```

**Parsing Template Example:**
```json
{
  "provider": "EnergyAustralia",
  "service_type": "Electricity",
  "patterns": {
    "invoice_date": "Invoice Date:\\s*(\\d{2}/\\d{2}/\\d{4})",
    "total_amount": "Total Amount Due:\\s*\\$([\\d,]+\\.\\d{2})",
    "usage_quantity": "Usage:\\s*([\\d,]+\\.?\\d*)\\s*kWh",
    "usage_rate": "Rate:\\s*\\$([\\d.]+)\\s*per kWh"
  },
  "validation": {
    "amount_range": [10, 1000],
    "usage_range": [100, 5000]
  }
}
```

### Data Storage Layer

**Database Abstraction:**
```python
class DatabaseAdapter:
    def __init__(self):
        if os.getenv('AWS_MODE'):
            self.engine = create_engine(self._get_rds_connection_string())
        else:
            self.engine = create_engine('sqlite:///./data/invoices.db')
            
    def save_invoice(self, invoice: Invoice):
        # Unified save interface for both databases
        # Handles connection pooling and transactions
```

**Responsibilities:**
- Database abstraction supporting SQLite (local) and PostgreSQL RDS (AWS)
- Automated CSV export with configurable destination (filesystem/S3)
- Data integrity enforcement and duplicate prevention
- Migration system compatible with both environments
- Backup and recovery procedures

**Storage Outputs:**
1. **Database**: Structured storage for web application queries
2. **CSV Export**: Power BI data source with automated updates
3. **Backup Files**: Regular data exports for disaster recovery

### Web Application Architecture

**Local Development Stack:**
- **Backend**: Flask/FastAPI with SQLite
- **Frontend**: React SPA served locally
- **Authentication**: Simple JWT or session-based
- **Static Assets**: Local file serving

**AWS Production Stack:**
- **Backend**: ECS Fargate with RDS PostgreSQL  
- **Frontend**: React SPA on CloudFront + S3
- **Authentication**: AWS Cognito with JWT
- **Load Balancer**: ALB with HTTPS termination
- **API Gateway**: RESTful endpoints with throttling

**API Endpoints:**
```
GET  /api/invoices          # Filtered invoice data
POST /api/sync              # Manual sync trigger
GET  /api/providers         # Configured providers
GET  /api/analytics         # Aggregated statistics
GET  /api/export/csv        # CSV data export
```

### Power BI Integration

**Local Integration:**
- Direct CSV file connection from `./data/invoices.csv`
- Manual refresh or scheduled file monitoring
- Local Power BI Desktop development

**AWS Integration:**
- S3 data connector with automated CSV exports
- Lambda-triggered data refresh pipeline  
- Power BI Service integration with row-level security
- Scheduled refresh with error notifications

**Dashboard Components:**
- **KPI Cards**: Total spend, average usage, bill count
- **Line Charts**: Spend trends over time by service type
- **Bar Charts**: Usage comparison across billing periods
- **Slicers**: Service type, date range, provider filters
- **Heat Maps**: Usage patterns by month/season

## AWS Infrastructure Design

### Compute Services
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   EventBridge   │───▶│ Lambda Functions │───▶│   SQS Queue    │
│   (Schedule)    │    │ (Email Fetcher)  │    │ (PDF Process)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│      S3         │◀───│ Lambda Functions │───▶│  RDS PostgreSQL │
│  (PDF Storage)  │    │  (PDF Parser)    │    │ (Structured)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   ECS Fargate    │
                       │  (Web App)       │
                       └──────────────────┘
```

### Security Architecture
- **VPC**: Multi-AZ with public/private subnets
- **Security Groups**: Restrictive inbound/outbound rules  
- **IAM Roles**: Service-specific least-privilege access
- **Secrets Manager**: OAuth tokens and database credentials
- **KMS**: Encryption for all data at rest and in transit
- **Cognito**: User authentication and authorization

### Monitoring & Observability
- **CloudWatch Logs**: Centralized logging with retention policies
- **CloudWatch Metrics**: Custom metrics for business logic
- **X-Ray**: Distributed tracing for performance debugging
- **SNS**: Alerting for system failures and errors
- **CloudWatch Dashboards**: Real-time system monitoring

## Configuration Management

### Local Configuration (JSON Files)
```json
{
  "environment": "local",
  "database": {
    "type": "sqlite",
    "path": "./data/invoices.db"
  },
  "storage": {
    "type": "filesystem",
    "base_path": "./data/invoices/"
  },
  "ocr": {
    "type": "local",
    "engines": ["pdfplumber", "pytesseract"]
  }
}
```

### AWS Configuration (Parameter Store)
```json
{
  "environment": "aws",
  "database": {
    "type": "postgresql",
    "endpoint": "{{resolve:ssm:rds-endpoint}}",
    "credentials": "{{resolve:secretsmanager:db-credentials}}"
  },
  "storage": {
    "type": "s3",
    "bucket": "utilities-invoices-bucket"
  },
  "ocr": {
    "type": "textract",
    "region": "us-east-1"
  }
}
```

## Development Guidelines

### Code Organization
- **Separation of Concerns**: Clear boundaries between services
- **Interface-Based Design**: Abstract classes for all adapters
- **Configuration Injection**: No hardcoded environment specifics
- **Error Handling**: Comprehensive exception handling with logging
- **Testing**: Unit tests for all adapters and business logic

### Transition Strategy
1. **Develop Locally**: Complete functionality with SQLite and local storage
2. **Create Abstractions**: Build adapter interfaces for all external services  
3. **Implement AWS Adapters**: Create AWS versions without deploying
4. **Test Locally**: Validate all functionality with real invoice data
5. **Deploy to AWS**: Switch via configuration after approval

This design ensures rapid local development while maintaining production-ready architecture for seamless AWS deployment when approved.
# CLAUDE.md - Utilities Tracker Build Instructions

You are a senior full-stack software engineer tasked with building the **Utilities Tracker** project from scratch. This is a comprehensive application that automates utility expense tracking by fetching invoices from email, parsing PDF data, and providing interactive analytics through both Power BI and web interfaces.

## Important Development Approach

**DOCUMENTATION UPDATES REQUIRED**: You must update ALL existing .md files (README.md, USAGE.md, SOFTWARE DESIGN.md, USECASES.md, CONTRIBUTING.md, etc.) to reflect the AWS architecture and deployment strategy outlined in this prompt. Ensure all documentation is consistent and includes both local development and AWS deployment instructions.

**DEVELOPMENT STRATEGY**: 
1. **Build for AWS, Test Locally**: Design the application architecture with AWS deployment in mind from day one, but implement local alternatives for development and testing
2. **Local Development First**: Create a fully functional local version using SQLite, local file storage, and direct API calls
3. **AWS-Ready Architecture**: Structure code so that transitioning to AWS requires minimal changes - primarily configuration switches rather than code rewrites
4. **Deploy Only When Approved**: AWS deployment should happen last, only after local testing is complete and explicit approval is given

This approach ensures rapid local development while maintaining production-ready architecture for seamless AWS transition.

## Project Mission

Build a complete end-to-end system that:
1. **Automatically fetches** utility invoices (Electricity, Gas, Water) from email providers
2. **Parses PDF invoices** to extract structured data (dates, amounts, usage, rates)
3. **Stores data** in both CSV (for Power BI) and database formats
4. **Provides dual analytics interfaces**: Power BI dashboard and web application
5. **Supports multiple providers** with modular, extensible architecture

## Technical Stack & Architecture

### Backend (Python)
- **Email Integration**: Gmail/Outlook APIs with OAuth2 authentication
- **PDF Processing**: `pdfplumber`, `pytesseract` for text extraction (local), AWS Textract (production)
- **Data Processing**: `pandas`, `sqlalchemy` for data manipulation and storage
- **Database**: SQLite for local development, PostgreSQL/RDS for AWS production
- **API Framework**: Flask or FastAPI for web backend
- **Storage**: Local filesystem for development, S3 for AWS production
- **Task Queue**: Local threading/celery for development, SQS/Lambda for AWS production

### Frontend Options
- **Web App**: React, Vue, Streamlit, or Dash for interactive dashboards
- **Analytics**: Power BI Desktop/Service integration

### AWS Cloud Architecture
- **Compute**: AWS Lambda for serverless functions, EC2 for web application hosting
- **Storage**: S3 for PDF storage, RDS PostgreSQL for structured data
- **Authentication**: AWS Cognito for user management, Secrets Manager for credentials
- **Scheduling**: EventBridge/CloudWatch for automated invoice fetching
- **Monitoring**: CloudWatch Logs and X-Ray for observability
- **API Gateway**: RESTful API endpoints with throttling and authentication

### Repository Structure
```
Utilities-Tracker/
├── email_fetcher/          # Email API integration and PDF downloading
├── pdf_parser/            # PDF parsing and data extraction
├── data_storage/          # Database models and CSV output
├── web_app/              # Web application (frontend/backend)
├── powerbi_dashboard/    # Power BI .pbix files
├── config/               # Provider configs and credentials (local + AWS)
├── infrastructure/       # AWS CDK/CloudFormation templates
├── lambda_functions/     # Serverless function implementations (AWS deployment)
├── local_dev/           # Local development utilities and scripts
└── docs/                # Documentation and specifications
```

## Development Architecture: Local First, AWS Ready

### Local Development Environment
- **Database**: SQLite for rapid development and testing
- **File Storage**: Local filesystem with organized folder structure
- **Task Processing**: Python threading or Celery with Redis
- **Authentication**: Local JWT tokens or simple session management
- **Configuration**: JSON files with environment variable overrides

### AWS Production Environment  
- **Database**: RDS PostgreSQL with Multi-AZ
- **File Storage**: S3 with intelligent tiering
- **Task Processing**: Lambda functions with SQS/EventBridge
- **Authentication**: AWS Cognito with proper IAM roles
- **Configuration**: Parameter Store with Secrets Manager

## Core Modules to Build

### 1. Email Fetcher Service (`email_fetcher/` + `lambda_functions/`)
**Local Development Implementation:**
- **Direct API Calls**: Gmail/Outlook API integration with local credential storage
- **Local File Storage**: Save PDFs to `./data/invoices/` with organized folder structure
- **SQLite Tracking**: Store email metadata and processing status locally
- **Python Threading**: Background processing for multiple email accounts
- **Configuration**: JSON files in `config/` folder with environment overrides

**AWS Production Implementation:**  
- **Lambda Function**: Triggered by EventBridge on schedule (weekly/daily)
- **S3 Storage**: Store downloaded PDF attachments with versioning
- **Secrets Manager**: Store OAuth tokens and email credentials securely  
- **SQS**: Queue system for batch processing multiple invoices
- **Parameter Store**: Provider configurations and search criteria

**AWS-Ready Code Structure:**
```python
# email_fetcher/storage.py
class StorageAdapter:
    def save_pdf(self, pdf_data, filename):
        if os.getenv('AWS_MODE'):
            return self._save_to_s3(pdf_data, filename)
        else:
            return self._save_to_local(pdf_data, filename)
```

**Responsibilities:**
- OAuth2 connection to Gmail/Outlook APIs
- Search emails by sender, subject keywords, date range, attachments
- Download PDF attachments with configurable storage backend
- Maintain processing history to avoid re-processing
- Comprehensive logging with CloudWatch-ready format

**Key Features:**
- Initial historical data scrape
- Incremental updates (only new invoices)
- Provider-specific email search criteria from JSON config
- Secure credential management

### 2. PDF Parser Service (`pdf_parser/` + `lambda_functions/`)
**Local Development Implementation:**
- **Local PDF Processing**: Use `pdfplumber` and `pytesseract` for text extraction
- **File System Monitoring**: Watch local PDF folder for new files to process
- **SQLite Storage**: Store extracted data with immediate availability  
- **Provider Templates**: JSON-based parsing rules stored locally
- **Error Handling**: Local logging with retry mechanisms

**AWS Production Implementation:**
- **Lambda Function**: Triggered by S3 events when PDFs are uploaded
- **AWS Textract**: Superior OCR and document analysis capabilities
- **Parameter Store**: Provider-specific parsing templates with versioning
- **Dead Letter Queue**: Handle failed parsing attempts with alerting
- **RDS Integration**: Store structured data with connection pooling

**AWS-Ready Code Structure:**  
```python
# pdf_parser/ocr_adapter.py
class OCRAdapter:
    def extract_text(self, pdf_path):
        if os.getenv('AWS_MODE'):
            return self._textract_extract(pdf_path)
        else:
            return self._local_extract(pdf_path)
```

**Responsibilities:**
- Extract structured data from utility PDFs:
  - Invoice date, total amount due, service charges, usage quantities
  - Rate per unit (kWh, m³, litres), provider identification
- Configurable parsing templates for multiple providers
- Data validation with comprehensive error handling and retry logic
- Seamless transition between local OCR and AWS Textract

### 3. Data Storage Layer (`data_storage/`)
**Local Development Implementation:**
- **SQLite Database**: Fast setup with zero configuration requirements
- **Local CSV Export**: Direct file system writes for Power BI integration
- **File-based Backups**: Simple database dumps and CSV archiving
- **Migration Scripts**: Version-controlled schema changes

**AWS Production Implementation:**
- **RDS PostgreSQL**: Primary database with Multi-AZ for high availability
- **S3 Integration**: Automated CSV exports with lifecycle management
- **Lambda Functions**: Scheduled data export and backup automation
- **VPC Security**: Network isolation with private subnets

**AWS-Ready Code Structure:**
```python
# data_storage/db_adapter.py  
class DatabaseAdapter:
    def __init__(self):
        if os.getenv('AWS_MODE'):
            self.engine = self._create_rds_engine()
        else:
            self.engine = self._create_sqlite_engine()
```

**Responsibilities:**
- Database abstraction layer supporting SQLite and PostgreSQL
- Automated CSV export with configurable destination (local/S3)
- Data integrity, duplicate prevention, and constraint validation
- Migration system that works across both environments
- Backup and recovery procedures for both local and cloud storage

**Schema Requirements:**
```sql
invoices (
  id, provider_name, service_type, invoice_date,
  total_amount, usage_quantity, usage_rate,
  service_charge, billing_period_start, billing_period_end,
  file_path, processing_status, created_at, updated_at
)
```

### 4. Web Application (`web_app/` + EC2/ECS)
**AWS Implementation:**
- **Application Load Balancer**: HTTPS termination and traffic distribution  
- **ECS Fargate**: Containerized web application with auto-scaling
- **CloudFront**: CDN for static assets and global content delivery
- **Route 53**: DNS management and health checks
- **Cognito**: User authentication and authorization
- **API Gateway**: RESTful API with rate limiting and caching

**Frontend Requirements:**
- React/Vue SPA hosted on CloudFront + S3
- Interactive charts using Chart.js/D3.js (line charts for trends, bar charts for usage)
- Filter controls (service type, date range, billing period)
- Data tables with sorting and pagination
- Manual sync button triggering Lambda functions
- Responsive design optimized for mobile/desktop

**Backend API Implementation:**
- `GET /api/invoices` - Retrieve filtered invoice data from RDS
- `POST /api/sync` - Trigger Lambda function for manual invoice fetch
- `GET /api/providers` - List configured providers from Parameter Store
- `GET /api/analytics` - Aggregated statistics with ElastiCache caching
- Authentication via Cognito JWT tokens

### 5. Power BI Integration (`powerbi_dashboard/` + S3)
**AWS Implementation:**
- **S3 Data Source**: Automated CSV exports from RDS to S3 bucket
- **S3 Gateway Endpoint**: Secure VPC access to S3 without internet routing
- **EventBridge**: Schedule Power BI data refresh triggers
- **Lambda**: Custom data transformation before CSV export

**Deliverables:**
- Complete `.pbix` dashboard file with S3 data connector
- Automated CSV export pipeline from RDS to S3
- Interactive visuals: slicers, line charts, KPI cards, heat maps
- Scheduled refresh configuration with error notifications
- Row-level security implementation for multi-tenant scenarios

### AWS Infrastructure Setup (`infrastructure/`)
**Infrastructure as Code:**
- **AWS CDK/CloudFormation**: Complete infrastructure definition
- **VPC Configuration**: Multi-AZ setup with public/private subnets
- **Security Groups**: Least privilege access controls
- **IAM Roles**: Service-specific permissions with minimal access
- **KMS**: Encryption keys for data at rest and in transit

**Monitoring & Logging:**
- **CloudWatch**: Comprehensive logging and metrics collection
- **X-Ray**: Distributed tracing for debugging performance issues
- **SNS**: Notifications for system alerts and failures
- **CloudWatch Alarms**: Automated alerting for critical metrics

## Configuration System

### AWS Parameter Store Configuration
```json
{
  "providers": {
    "EnergyAustralia": {
      "email": "noreply@energyaustralia.com.au", 
      "service_type": "Electricity",
      "subject_keywords": ["bill", "invoice", "statement"],
      "parsing_template": "energy_australia_template",
      "s3_prefix": "invoices/energy-australia/"
    }
  }
}
```

### AWS Secrets Manager
- OAuth tokens with automatic rotation
- Database credentials with encryption
- API keys and external service credentials
- Environment-specific configuration separation

## Development Requirements

### Code Quality Standards
- **PEP8 compliance** for all Python code
- **Comprehensive error handling** with detailed logging
- **Unit tests** for critical functions (email fetch, PDF parsing, data storage)
- **Documentation** for all modules, classes, and functions
- **Type hints** throughout Python codebase

### AWS Security Requirements
- **IAM Best Practices**: Least privilege access with service-specific roles
- **VPC Security**: Private subnets for databases, public subnets for load balancers
- **Encryption**: KMS encryption for all data at rest and in transit
- **Secrets Management**: AWS Secrets Manager for all credentials and tokens
- **WAF Integration**: Web Application Firewall for API Gateway protection
- **Security Groups**: Restrictive inbound/outbound rules with audit logging

### AWS Performance Requirements
- **Lambda Performance**: Cold start optimization with provisioned concurrency
- **RDS Optimization**: Connection pooling and read replicas for analytics
- **S3 Performance**: Intelligent tiering for cost optimization
- **CloudFront Caching**: Aggressive caching strategy for static assets
- **ElastiCache**: Redis caching for frequently accessed data
- **Auto Scaling**: Dynamic scaling based on CloudWatch metrics

## Implementation Phases

### Phase 1: Local Development Foundation
1. **Repository Setup**: Initialize structure with both local and AWS configurations
2. **Local Database**: SQLite setup with complete schema and sample data
3. **Email Fetcher (Local)**: Gmail API integration with local file storage
4. **PDF Parser (Local)**: Basic parsing with pdfplumber/pytesseract
5. **Documentation Updates**: Update all .md files to reflect dual-environment approach

### Phase 2: Core Functionality (Local Testing)
1. **Multi-Provider Support**: Extend parsing for 2-3 different utility companies
2. **Data Pipeline**: Complete local processing workflow with error handling
3. **Web Application**: Frontend and backend with local database integration
4. **Power BI Integration**: CSV export and dashboard creation
5. **Comprehensive Testing**: Unit tests, integration tests, end-to-end validation

### Phase 3: AWS-Ready Architecture (Preparation)
1. **Abstraction Layers**: Create adapters for storage, database, OCR services
2. **Configuration Management**: Environment-based settings for local/AWS
3. **Infrastructure Code**: Complete CDK/CloudFormation templates
4. **Lambda Functions**: Serverless versions of core services (ready but unused)
5. **Security Implementation**: IAM roles, VPC setup, encryption at rest

### Phase 4: AWS Migration (Post-Approval Only)
1. **Infrastructure Deployment**: Create AWS resources via IaC
2. **Data Migration**: Transfer local data to RDS and S3
3. **Service Deployment**: Switch from local to AWS services
4. **Production Testing**: End-to-end validation in AWS environment
5. **Monitoring Setup**: CloudWatch dashboards, alarms, and logging

## Success Criteria

**Functional Success:**
- ✅ Automatically fetch and parse invoices from 3+ providers
- ✅ Web dashboard displays 2+ years of historical data
- ✅ Power BI dashboard with interactive filtering
- ✅ Manual sync completes in < 60 seconds
- ✅ Data accuracy > 95% for all extracted fields

**Technical Success:**
- ✅ Modular architecture allows adding new providers in < 2 hours
- ✅ Zero data loss or corruption
- ✅ Secure credential handling with no hardcoded secrets
- ✅ Comprehensive error logging and recovery
- ✅ Responsive web interface across devices

## Getting Started

### Initial Development Setup
1. **Clone and Initialize**: Set up repository structure with local and AWS configurations
2. **Update Documentation**: Revise all .md files to include local development and AWS deployment instructions  
3. **Python Environment**: Set up virtual environment with all dependencies
4. **Local Database**: Initialize SQLite with schema and sample data
5. **Configuration Files**: Create JSON configs for both local and AWS environments

### Local Development First
1. **Email Integration**: Gmail API setup with local credential storage
2. **PDF Processing**: Local file-based processing with pdfplumber/pytesseract
3. **Database Operations**: SQLite integration with ORM and migrations
4. **Web Application**: Local Flask/FastAPI server with frontend
5. **Power BI Integration**: CSV export to local filesystem

### AWS Preparation (Build but Don't Deploy)  
1. **Infrastructure Code**: Create CDK/CloudFormation templates (don't deploy)
2. **Lambda Functions**: Write serverless versions of core services
3. **Abstraction Layers**: Implement storage/database/OCR adapters
4. **Configuration System**: Environment-based settings for seamless transition
5. **Security Planning**: IAM roles, VPC design, encryption strategy

### AWS Deployment (Only After Approval)
1. **Infrastructure Creation**: Deploy AWS resources using IaC
2. **Data Migration**: Move local data to RDS and S3
3. **Service Activation**: Switch from local to AWS services via configuration
4. **Production Validation**: Complete testing in AWS environment
5. **Monitoring Activation**: Enable CloudWatch dashboards and alerting

**Key Principle**: Every component should work locally first, then be enhanced with AWS capability through configuration, not code changes.

## Notes for Development

### Documentation Management
- **Update ALL .md files** to reflect the local-first, AWS-ready architecture
- **README.md**: Include both local setup and AWS deployment instructions
- **USAGE.md**: Document local development workflow and AWS production usage
- **SOFTWARE DESIGN.md**: Update with abstraction layers and dual-environment design
- **CONTRIBUTING.md**: Include guidelines for maintaining compatibility across environments
- **Maintain consistency** between local development docs and AWS deployment guides

### Local Development Best Practices
- **Test with real invoice PDFs** locally before considering AWS deployment
- **SQLite for development**: Fast, zero-config database ideal for testing
- **Local file storage**: Organized folder structure that mimics S3 key patterns  
- **Environment variables**: Use `.env` files for local config, Parameter Store for AWS
- **Comprehensive logging**: Format logs for both local debugging and CloudWatch compatibility

### AWS-Ready Architecture Principles
- **Abstraction layers**: Never hard-code local vs AWS logic in business code
- **Configuration-driven**: Switch environments through config, not code changes
- **Resource naming**: Use consistent naming that works locally and in AWS
- **Security from start**: Design local auth to easily transition to Cognito/IAM
- **Data portability**: Ensure easy migration from SQLite to RDS

### Development Workflow
1. **Build locally first**: Complete feature development and testing locally
2. **Test thoroughly**: Validate all functionality before considering AWS deployment
3. **Prepare AWS version**: Create AWS-compatible versions but don't deploy
4. **Seek approval**: Only deploy to AWS after explicit approval and sign-off
5. **Minimal changes**: AWS transition should require only configuration changes

**Critical Success Factor**: The application must work perfectly locally before any AWS deployment is considered. AWS deployment is an enhancement, not a requirement for core functionality.
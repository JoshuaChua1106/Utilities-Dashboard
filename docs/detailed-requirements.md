# Use Cases and Requirements - Utilities Tracker

## System Overview

The Utilities Tracker system serves multiple user personas and deployment scenarios with a **local-first, AWS-ready architecture**. The system provides identical functionality in both local development and AWS production environments through configuration-driven deployment.

## Primary User Personas

### 1. Individual Homeowner (Local Development Focus)
**Profile**: Personal utility tracking for budgeting and analysis
**Environment**: Local installation on personal computer
**Technical Level**: Basic to intermediate computer skills

### 2. Small Business/Property Manager (Local to Cloud Transition)
**Profile**: Managing multiple properties or business locations
**Environment**: Starts local, may migrate to AWS for scalability
**Technical Level**: Intermediate technical skills or access to IT support

### 3. Enterprise/Large Organization (AWS Production)
**Profile**: Centralized utility management across multiple facilities
**Environment**: AWS production deployment with enterprise features
**Technical Level**: Professional IT team and infrastructure management

## Core Use Cases by Environment

### Local Development Use Cases

#### UC-1: Personal Utility Tracking Setup
**Actor**: Individual Homeowner
**Environment**: Local development
**Preconditions**: Python environment and Gmail/Outlook access
**Main Flow**:
1. User installs application locally using `pip install -r requirements.txt`
2. System initializes SQLite database automatically
3. User configures email providers in `config/providers.json`
4. System authenticates with Gmail/Outlook using OAuth2
5. User triggers initial historical data scrape
6. System downloads and parses all historical invoices to local filesystem
7. User accesses data via local web app at `http://localhost:5000`

**Postconditions**: Local database populated with historical data, web app accessible
**Alternative Flows**: 
- 3a. User has multiple email accounts → Configure multiple provider sections
- 5a. Authentication fails → System guides user through OAuth2 re-authorization

#### UC-2: Local Invoice Processing
**Actor**: Individual Homeowner
**Environment**: Local development
**Preconditions**: System configured and authenticated
**Main Flow**:
1. User clicks "Update Invoices" in web application
2. System searches email for new invoices since last update
3. System downloads new PDF attachments to `./data/invoices/`
4. PDF parser extracts structured data using local OCR (pdfplumber/pytesseract)
5. System saves invoice data to SQLite database
6. System exports updated data to `./data/invoices.csv` for Power BI
7. Web application displays updated charts and tables
8. User reviews new invoices and validates parsing accuracy

**Postconditions**: New invoices processed and available in both web app and Power BI
**Performance Requirements**: Processing completes within 30 seconds for 5 new invoices

#### UC-3: Local Data Analysis with Power BI
**Actor**: Individual Homeowner
**Environment**: Local development with Power BI Desktop
**Preconditions**: Invoice data available in CSV format
**Main Flow**:
1. User opens Power BI Desktop
2. User connects to `./data/invoices.csv` as data source
3. User opens provided dashboard template from `powerbi_dashboard/utilities-tracker.pbix`
4. Dashboard displays interactive visuals:
   - KPI cards showing total spend per service type
   - Line charts for spend trends over time
   - Bar charts for usage comparison across periods
   - Slicers for filtering by service type and date range
5. User analyzes spending patterns and usage trends
6. User exports insights or saves custom views

**Postconditions**: User gains insights into utility usage and spending patterns
**Performance Requirements**: Dashboard loads within 5 seconds for 2 years of data

### AWS Production Use Cases

#### UC-4: Enterprise Multi-Property Management
**Actor**: Property Manager
**Environment**: AWS production deployment
**Preconditions**: AWS infrastructure deployed, multiple email accounts configured
**Main Flow**:
1. EventBridge triggers Lambda function weekly for automated processing
2. Lambda function processes multiple email accounts in parallel
3. System downloads PDFs to S3 with organized folder structure
4. AWS Textract provides superior OCR for complex invoice formats
5. Parsed data stored in RDS PostgreSQL with multi-tenant isolation
6. Web application (ECS Fargate) displays consolidated view across all properties
7. Power BI Service connects to S3 for automated dashboard refresh
8. Property manager reviews consolidated spending across portfolio

**Postconditions**: All properties' utility data processed and available for analysis
**Performance Requirements**: Processes 100+ invoices across 20 properties within 10 minutes

#### UC-5: Automated Compliance Reporting
**Actor**: Enterprise Finance Team
**Environment**: AWS production with compliance features
**Preconditions**: AWS deployment with audit logging enabled
**Main Flow**:
1. System processes utility invoices with full audit trail
2. CloudWatch logs capture all processing activities
3. Data validation ensures accuracy for regulatory compliance
4. System generates monthly compliance reports automatically
5. Reports exported to S3 with appropriate access controls
6. Finance team accesses reports via secure web portal
7. System maintains data retention policies per regulatory requirements

**Postconditions**: Compliance reports generated and available for audit
**Security Requirements**: SOC2 compliance, audit logging, encrypted data at rest/transit

## Functional Requirements by Environment

### Core Functionality (Both Environments)

#### FR-1: Email Integration
- **Local**: Direct OAuth2 connection to Gmail/Outlook APIs with token storage in local JSON files
- **AWS**: OAuth2 integration with tokens stored in AWS Secrets Manager with automatic rotation
- **Common**: Search emails using provider-specific criteria, download PDF attachments
- **Data Flow**: Email → Authentication → Search → Download → Storage (local filesystem or S3)

#### FR-2: PDF Processing
- **Local**: Text extraction using pdfplumber and pytesseract for OCR processing
- **AWS**: Enhanced processing using AWS Textract for superior accuracy
- **Common**: Provider-specific parsing templates, data validation, error handling
- **Output**: Standardized invoice objects with structured data fields

#### FR-3: Data Storage and Export
- **Local**: SQLite database for web app, CSV files for Power BI, local filesystem storage
- **AWS**: RDS PostgreSQL for web app, S3-based CSV export, automated backup procedures
- **Common**: Duplicate prevention, data integrity validation, configurable retention policies
- **Formats**: Database tables, CSV export, JSON API responses

#### FR-4: Web Application Interface
- **Local**: Flask/FastAPI backend with React frontend, served locally
- **AWS**: ECS Fargate deployment with CloudFront distribution, auto-scaling enabled
- **Common**: Interactive charts, filtering controls, manual sync triggers, responsive design
- **Features**: Service type filtering, date range selection, usage vs spend analysis

#### FR-5: Power BI Integration
- **Local**: Direct CSV file connection with manual or scheduled refresh
- **AWS**: S3 data connector with automated Lambda-triggered exports
- **Common**: Pre-built dashboard templates, interactive slicers, KPI cards
- **Visualizations**: Trend lines, usage comparisons, spend analysis, seasonal patterns

### Environment-Specific Features

#### Local Development Features
- **Quick Setup**: Zero-configuration database with sample data
- **Offline Processing**: Complete functionality without internet connectivity
- **Debug Mode**: Detailed local logging and error reporting
- **Development Tools**: Built-in testing utilities and validation scripts

#### AWS Production Features
- **Scalability**: Auto-scaling web application and serverless processing
- **High Availability**: Multi-AZ database deployment and load balancing
- **Security**: WAF protection, VPC isolation, IAM-based access control
- **Monitoring**: CloudWatch dashboards, X-Ray tracing, automated alerting
- **Enterprise**: Multi-tenant support, compliance logging, backup automation

## Non-Functional Requirements

### Performance Requirements

#### Local Environment
- **Invoice Processing**: 10 seconds per invoice on standard home computer
- **Web Application**: 2-second response time for 2 years of data
- **Database Queries**: Sub-second response for typical filtering operations
- **Power BI Refresh**: Under 30 seconds for complete data refresh

#### AWS Environment  
- **Scalability**: Support 1000+ properties with 50,000+ annual invoices
- **Concurrent Users**: 100+ simultaneous web application users
- **Batch Processing**: 500+ invoices processed within 15-minute window
- **API Response**: 500ms average response time with global distribution

### Reliability Requirements

#### Both Environments
- **Email Retry Logic**: 3 retry attempts for failed email fetches
- **Data Integrity**: Zero tolerance for duplicate records or data corruption
- **Error Recovery**: Automatic retry with exponential backoff
- **Validation**: Comprehensive data validation with accuracy > 95%

#### AWS-Specific Reliability
- **Uptime**: 99.9% availability SLA with automated failover
- **Disaster Recovery**: Cross-region backup with 4-hour RTO
- **Service Resilience**: Circuit breakers and graceful degradation
- **Data Durability**: 99.999999999% (11 9's) durability via S3

### Security Requirements

#### Local Development Security
- **Credential Storage**: Encrypted storage of OAuth tokens and email credentials
- **Local Access**: File system permissions and database encryption
- **Network Security**: Local-only access by default, optional secure remote access
- **Data Protection**: No sensitive data exposure in logs or temporary files

#### AWS Production Security
- **Infrastructure**: VPC isolation, security groups, NACLs
- **Data Protection**: KMS encryption at rest, TLS 1.2+ in transit
- **Access Control**: IAM roles with least privilege principle
- **Compliance**: SOC2, GDPR compliance with audit logging
- **Monitoring**: Real-time security monitoring with automated threat response

### Maintainability and Extensibility

#### Architecture Requirements
- **Modularity**: Clear separation between email fetcher, PDF parser, data storage, web app
- **Abstraction Layers**: Consistent interfaces for storage, database, and OCR services
- **Configuration Management**: Environment-specific settings without code changes
- **Provider Support**: New utility providers added via JSON configuration only

#### Development Requirements
- **Code Quality**: PEP8 compliance, type hints, comprehensive error handling
- **Testing**: Unit tests for all components, integration tests for workflows
- **Documentation**: Complete API documentation and deployment guides
- **Version Control**: Semantic versioning with automated release processes

## Success Criteria and Acceptance Tests

### Local Development Success
- [ ] Complete setup within 15 minutes on fresh Windows/Mac/Linux system
- [ ] Process 2+ years of historical invoices with >95% parsing accuracy
- [ ] Web application responsive on desktop and mobile browsers
- [ ] Power BI dashboard displays meaningful insights with sample data
- [ ] All functionality works offline without cloud dependencies

### AWS Production Success
- [ ] Infrastructure deployment completes within 30 minutes via CDK
- [ ] System processes 100+ weekly invoices across multiple email accounts
- [ ] Web application supports 50+ concurrent users with sub-second response
- [ ] Power BI Service integration with automated refresh and row-level security
- [ ] Complete audit trail and compliance reporting capabilities
- [ ] Zero data loss during AWS migration from local environment

### Business Value Delivery
- [ ] 50%+ reduction in manual invoice processing time
- [ ] Identification of 10%+ potential utility cost savings through usage analysis
- [ ] Automated compliance reporting reducing audit preparation by 75%
- [ ] Real-time visibility into utility spending trends and anomalies
- [ ] Self-service analytics reducing dependency on IT for reporting

This comprehensive requirements specification ensures that the Utilities Tracker system delivers value across all deployment scenarios while maintaining architectural consistency between local development and AWS production environments.
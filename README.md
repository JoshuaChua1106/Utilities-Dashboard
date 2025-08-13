# Utilities Tracker

A comprehensive application that automates utility expense tracking by fetching invoices from email, parsing PDF data, and providing interactive analytics through both Power BI and web interfaces.

## Architecture Overview

**Local-First, AWS-Ready Design**: Built for local development and testing with seamless AWS deployment capability. The application works fully locally using SQLite and local file storage, then can transition to AWS services through configuration changes only.

### Local Development Environment
- **Database**: SQLite for rapid development
- **File Storage**: Local filesystem with organized structure
- **Task Processing**: Python threading or Celery with Redis
- **Authentication**: Local JWT or session management
- **Configuration**: JSON files with environment overrides

### AWS Production Environment (Deploy Only After Approval)
- **Database**: RDS PostgreSQL with Multi-AZ
- **File Storage**: S3 with intelligent tiering
- **Task Processing**: Lambda functions with SQS/EventBridge
- **Authentication**: AWS Cognito with IAM roles
- **Configuration**: Parameter Store with Secrets Manager

## Features

- **Email Integration**: Automated invoice fetching from Gmail/Outlook APIs
- **PDF Processing**: Extract structured data (dates, amounts, usage, rates)
- **Dual Analytics**: Power BI dashboard and web application interfaces
- **Multi-Provider Support**: Configurable parsing templates for different utilities
- **Dual Storage**: CSV export for Power BI and database for web app
- **AWS-Ready Architecture**: Seamless transition from local to cloud deployment

## Tech Stack

### Backend (Python)
- **Email APIs**: Gmail/Outlook with OAuth2 authentication
- **PDF Processing**: `pdfplumber`, `pytesseract` (local) / AWS Textract (production)
- **Data Processing**: `pandas`, `sqlalchemy`
- **Web Framework**: Flask or FastAPI
- **Database**: SQLite (local) / PostgreSQL RDS (AWS)
- **Storage**: Local filesystem / S3

### Frontend & Analytics
- **Web App**: React, Vue, or Streamlit
- **Power BI**: Desktop/Service integration
- **Authentication**: Local JWT / AWS Cognito

### AWS Services (Production Only)
- **Compute**: Lambda functions, EC2/ECS for web app
- **Storage**: S3, RDS PostgreSQL
- **Security**: Cognito, Secrets Manager, IAM
- **Monitoring**: CloudWatch, X-Ray
- **API**: API Gateway with throttling

## Repository Structure

```
Utilities-Tracker/
├── email_fetcher/          # Email API integration and PDF downloading
├── pdf_parser/            # PDF parsing and data extraction
├── data_storage/          # Database models and CSV output
├── web_app/              # Web application (frontend/backend)
├── powerbi_dashboard/    # Power BI .pbix files
├── config/               # Provider configs and credentials (local + AWS)
├── infrastructure/       # AWS CDK/CloudFormation templates
├── lambda_functions/     # Serverless function implementations
├── local_dev/           # Local development utilities and scripts
└── docs/                # Documentation and specifications
```

## Quick Start - Local Development

### Prerequisites
- Python 3.9+
- Virtual environment tool (venv, conda)
- Gmail/Outlook API credentials

### Local Setup
1. **Clone and Setup Environment**:
   ```bash
   git clone <repository-url>
   cd Utilities-Tracker
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Initialize Local Database**:
   ```bash
   python local_dev/init_db.py
   ```

3. **Configure Email Providers**:
   ```bash
   cp config/providers.example.json config/providers.json
   cp config/credentials.example.json config/credentials.json
   # Edit files with your email provider settings
   ```

4. **Run Local Development**:
   ```bash
   # Fetch invoices locally
   python email_fetcher/fetch_invoices.py
   
   # Parse PDFs locally
   python pdf_parser/parse_pdfs.py
   
   # Start web application
   python web_app/app.py
   ```

5. **Access Applications**:
   - Web App: `http://localhost:5000`
   - Power BI: Connect to `./data/invoices.csv`

## AWS Deployment (Production)

**⚠️ AWS deployment should only be done after local testing is complete and explicit approval is given.**

### AWS Infrastructure Setup
1. **Deploy Infrastructure**:
   ```bash
   cd infrastructure/
   cdk deploy --all
   ```

2. **Configure AWS Services**:
   ```bash
   python aws_setup/configure_services.py
   ```

3. **Migrate Data**:
   ```bash
   python aws_setup/migrate_data.py
   ```

4. **Switch to AWS Mode**:
   ```bash
   export AWS_MODE=true
   # Application now uses AWS services
   ```

## Development Workflow

1. **Local Development First**: Complete all feature development locally
2. **Test Thoroughly**: Validate functionality with real invoice data
3. **Prepare AWS Version**: Create AWS-compatible code (don't deploy)
4. **Seek Approval**: Only deploy to AWS after explicit sign-off
5. **Deploy**: Switch to AWS through configuration only

## Key Principles

- **Local-First**: Every feature works locally before AWS consideration
- **Configuration-Driven**: Switch environments via config, not code changes
- **Abstraction Layers**: Clean separation between local and AWS implementations
- **Security by Design**: Secure credential handling in both environments
- **AWS as Enhancement**: Core functionality never depends on AWS services


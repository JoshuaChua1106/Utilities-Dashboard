# Contributing to Utilities Tracker

Thank you for your interest in contributing! We welcome all types of contributions to help improve this local-first, AWS-ready utility tracking application.

## Types of Contributions

### Code Contributions
- Bug fixes and performance improvements
- New utility provider support with parsing templates
- Web application UI/UX enhancements
- Data pipeline optimizations and automation improvements
- AWS infrastructure and deployment enhancements
- Testing and validation improvements

### Documentation Contributions
- Setup and usage guide improvements
- Architecture documentation updates
- Provider-specific configuration guides
- Troubleshooting and FAQ updates
- Code examples and tutorials

### Configuration Contributions
- New utility provider parsing templates
- Regional provider configurations
- Performance optimization configurations
- Security enhancement configurations

## Development Environment Requirements

### Local Development Setup
Since this is a **local-first, AWS-ready** application, all development happens locally first:

1. **Python Environment**: Python 3.9+ with virtual environment
2. **Local Database**: SQLite for development and testing
3. **Local Storage**: Filesystem-based storage for PDFs and logs
4. **Development Tools**: Code formatter, linter, testing framework

### Dual-Environment Compatibility
All contributions must maintain compatibility with both local and AWS environments:

- **Abstraction Layers**: Use adapter patterns for storage, database, and OCR
- **Configuration-Driven**: Environment switching via configuration only
- **No Hardcoded Dependencies**: Never hardcode local paths or AWS-specific resources
- **Graceful Fallbacks**: Local development should never require AWS services

## How to Contribute

### 1. Fork and Setup
```bash
# Fork the repository on GitHub
git clone https://github.com/your-username/utilities-tracker.git
cd utilities-tracker

# Set up local development environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Initialize local database
python local_dev/init_db.py
```

### 2. Create Feature Branch
```bash
git checkout -b feature/your-feature-name
# or
git checkout -b bugfix/issue-description
# or  
git checkout -b provider/new-utility-company
```

### 3. Development Workflow

#### Local-First Development
Always develop and test locally before considering AWS compatibility:

```bash
# Test locally first
python -m pytest tests/local/
python local_dev/validate_setup.py

# Ensure dual-environment compatibility
python -m pytest tests/adapters/
python local_dev/test_aws_compatibility.py
```

#### Code Quality Standards
- **PEP8 Compliance**: Use `black`, `flake8`, and `isort`
- **Type Hints**: Include type annotations for all functions
- **Error Handling**: Comprehensive exception handling with logging
- **Documentation**: Docstrings for all classes and functions
- **Testing**: Unit tests for all new functionality

#### Abstraction Layer Guidelines
When working with external services, always use abstraction patterns:

```python
# Good: Uses adapter pattern
class EmailFetcher:
    def __init__(self):
        self.storage = StorageAdapter()  # Auto-detects local vs S3
        
# Bad: Hardcoded to local filesystem
class EmailFetcher:
    def save_pdf(self, data, filename):
        with open(f"./data/invoices/{filename}", "wb") as f:
            f.write(data)
```

### 4. Testing Requirements

#### Local Testing (Required)
```bash
# Run all local tests
python -m pytest tests/local/ -v

# Test specific components
python -m pytest tests/local/test_email_fetcher.py
python -m pytest tests/local/test_pdf_parser.py
python -m pytest tests/local/test_data_storage.py

# Integration testing
python -m pytest tests/integration/ -v
```

#### AWS Compatibility Testing (Required for AWS features)
```bash
# Test adapter abstractions (no AWS resources needed)
python -m pytest tests/adapters/ -v

# Validate AWS compatibility without deployment
python tests/aws/validate_aws_code.py
```

#### Real Data Testing
Test with actual utility invoice PDFs (anonymize sensitive data):
```bash
python tests/e2e/test_real_invoices.py --pdf-directory=tests/sample_invoices/
```

### 5. Adding New Utility Providers

When adding support for new utility providers, follow this structure:

1. **Provider Configuration** (`config/providers/new_provider.json`):
```json
{
  "provider_name": "NewUtilityCo",
  "service_type": "Electricity",
  "email_patterns": {
    "from": ["billing@newutilityco.com", "noreply@newutilityco.com"],
    "subject_keywords": ["bill", "invoice", "statement"],
    "attachment_types": [".pdf"]
  },
  "parsing_config": {
    "template": "new_utility_co_template",
    "backup_ocr": true,
    "validation_rules": {
      "amount_range": [10, 2000],
      "usage_range": [0, 10000]
    }
  }
}
```

2. **Parsing Template** (`config/templates/new_utility_co_template.json`):
```json
{
  "provider": "NewUtilityCo",
  "service_type": "Electricity",
  "patterns": {
    "invoice_date": "Invoice Date:\\s*(\\d{1,2}/\\d{1,2}/\\d{4})",
    "total_amount": "Total Amount:\\s*\\$([\\d,]+\\.\\d{2})",
    "usage_quantity": "Total Usage:\\s*([\\d,]+\\.?\\d*)\\s*kWh",
    "usage_rate": "Rate:\\s*\\$([\\d.]+)\\s*per kWh",
    "service_charge": "Service Charge:\\s*\\$([\\d.]+)",
    "billing_period_start": "Period:\\s*(\\d{1,2}/\\d{1,2}/\\d{4})",
    "billing_period_end": "to\\s*(\\d{1,2}/\\d{1,2}/\\d{4})"
  },
  "post_processing": {
    "amount_multiplier": 1.0,
    "date_format": "%d/%m/%Y",
    "currency_symbol": "$"
  }
}
```

3. **Test Cases** (`tests/providers/test_new_utility_co.py`):
```python
def test_new_utility_co_parsing():
    # Test with sample invoice
    parser = PDFParser()
    result = parser.parse_pdf("tests/sample_invoices/new_utility_co_sample.pdf")
    
    assert result.provider_name == "NewUtilityCo"
    assert result.service_type == "Electricity"
    assert result.total_amount > 0
    # Additional validation tests
```

### 6. Commit and Pull Request

#### Commit Message Guidelines
Follow conventional commit format:
```bash
# Features
git commit -m "feat: add support for NewUtilityCo electricity provider"
git commit -m "feat(web-app): add usage comparison charts"

# Bug fixes  
git commit -m "fix: handle malformed PDF dates in parsing"
git commit -m "fix(email-fetcher): OAuth token refresh error"

# Documentation
git commit -m "docs: update provider configuration guide"

# Tests
git commit -m "test: add integration tests for PDF parser"

# AWS-related (but tested locally)
git commit -m "feat(aws): add RDS adapter with connection pooling"
```

#### Pull Request Guidelines
1. **Title**: Clear, descriptive title following conventional format
2. **Description**: Include:
   - What changes were made and why
   - How to test the changes locally
   - Any new dependencies or configuration changes
   - Screenshots for UI changes
   - AWS compatibility notes (if applicable)

3. **Checklist**:
   - [ ] Code follows PEP8 and passes all linting checks
   - [ ] All tests pass locally (`python -m pytest`)
   - [ ] New functionality includes comprehensive tests
   - [ ] Documentation updated if applicable
   - [ ] Abstraction layers maintained for dual-environment support
   - [ ] No hardcoded local paths or AWS-specific resources
   - [ ] Changes tested with real utility invoice data (anonymized)

## Code Review Process

### Review Criteria
All pull requests will be reviewed for:

1. **Code Quality**: PEP8 compliance, proper error handling, type hints
2. **Architecture Compliance**: Proper use of abstraction layers
3. **Local-First Design**: Works completely locally without AWS dependencies
4. **AWS Compatibility**: Ready for AWS deployment without code changes
5. **Testing**: Comprehensive test coverage with local and integration tests
6. **Documentation**: Clear docstrings and updated usage guides
7. **Security**: No exposed credentials or sensitive data

### Review Process
1. **Automated Checks**: CI pipeline runs tests and code quality checks
2. **Maintainer Review**: Manual review of code and architecture
3. **Local Testing**: Reviewers test changes in local environment
4. **AWS Validation**: For AWS-related changes, validate compatibility
5. **Feedback Loop**: Collaborative improvement through constructive feedback

## Special Contribution Areas

### AWS Infrastructure Contributions
When contributing AWS-related code:
- **Never require AWS for local development**
- **Test abstractions locally without AWS resources**
- **Use CDK/CloudFormation for infrastructure as code**
- **Follow AWS security best practices**
- **Document cost implications of changes**

### Performance Optimizations
- **Profile locally first** using SQLite and local storage
- **Measure before and after** performance impacts
- **Consider both local and AWS performance implications**
- **Test with realistic data volumes** (2+ years of invoices)

### Security Enhancements
- **Follow OWASP security guidelines**
- **Test credential handling in both environments**
- **Validate input sanitization and data validation**
- **Ensure no sensitive data exposure in logs**

## Reporting Issues

### Issue Templates
Use appropriate issue templates:

1. **Bug Report**: Include steps to reproduce, expected vs actual behavior
2. **Feature Request**: Describe the feature and its business value
3. **Provider Request**: Request support for new utility company
4. **Documentation Issue**: Problems with setup or usage guides
5. **Performance Issue**: Include profiling data and system specifications

### Issue Information Required
- **Environment**: Local development or AWS production
- **Python Version**: Output of `python --version`
- **Dependencies**: Output of `pip freeze`
- **Configuration**: Sanitized config files (remove credentials)
- **Logs**: Relevant log entries (sanitize any sensitive data)
- **Sample Data**: Anonymized invoice samples if relevant

## Getting Help

### Discussion Channels
- **GitHub Discussions**: General questions and feature discussions
- **Issues**: Bug reports and specific problems
- **Wiki**: Community-contributed guides and tips

### Maintainer Contact
For complex architectural questions or significant contributions, reach out to maintainers before starting work to ensure alignment with project goals.

## Recognition

Contributors will be recognized in:
- **CHANGELOG.md**: All contributions noted in release notes
- **README.md**: Major contributors listed
- **GitHub Contributors**: Automatic recognition via GitHub

Thank you for helping make Utilities Tracker better for everyone!
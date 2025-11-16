# AI RFQ Engine

A comprehensive GraphQL-based Request for Quote (RFQ) management system built with Python, DynamoDB, and AWS Lambda. This engine provides intelligent quote generation, pricing management, and supplier relationship tools for B2B procurement workflows.

## 🚀 Features

### Core Functionality
- **Item Management**: Catalog management with support for multiple item types, specifications, and units of measure
- **Provider Management**: Supplier onboarding with item catalogs, pricing tiers, and batch tracking
- **RFQ Processing**: Automated quote request distribution and response collection
- **Quote Generation**: AI-powered quote generation with pricing optimization
- **Installment Planning**: Flexible payment scheduling and financial planning
- **File Management**: Document attachment and management for RFQ processes

### Advanced Features
- **Tiered Pricing**: Volume-based pricing with configurable tiers
- **Discount Rules**: Automated discount calculation based on business rules
- **Batch Tracking**: Lot/batch management for inventory control
- **Segment Management**: Customer segmentation for targeted pricing
- **Multi-Provider Support**: Competitive bidding across multiple suppliers

## 🏗️ Architecture

### Technology Stack
- **Backend**: Python 3.8+
- **Database**: Amazon DynamoDB
- **API**: GraphQL with Graphene
- **Cloud**: AWS Lambda (Serverless)
- **Framework**: SilvaEngine (Custom framework)

### Project Structure
```
ai_rfq_engine/
├── ai_rfq_engine/           # Main package
│   ├── handlers/            # Configuration and handlers
│   ├── models/              # Data models and business logic
│   ├── mutations/           # GraphQL mutations
│   ├── queries/             # GraphQL queries
│   ├── types/               # GraphQL type definitions
│   ├── tests/               # Test suite
│   ├── main.py              # Entry point and deployment config
│   └── schema.py            # GraphQL schema definition
├── pyproject.toml           # Project configuration
├── LICENSE                  # MIT License
└── README.md                # This file
```

## 📊 Data Model

### Core Entities

#### Items
- **Purpose**: Product/service catalog management
- **Key Fields**: `item_uuid`, `item_type`, `item_name`, `uom`, `item_description`
- **Features**: Hierarchical categorization, specification management

#### Providers & Provider Items
- **Purpose**: Supplier management and their product offerings
- **Key Fields**: `provider_item_uuid`, `item_uuid`, `base_price_per_uom`, `item_spec`
- **Features**: Multi-supplier support, competitive pricing

#### Segments & Contacts
- **Purpose**: Customer segmentation and contact management
- **Key Fields**: `segment_uuid`, `segment_name`, `email`
- **Features**: Targeted pricing, relationship management

#### Requests & Quotes
- **Purpose**: RFQ workflow management
- **Key Fields**: `request_uuid`, `quote_uuid`, `items[]`, `total_quote_amount`
- **Features**: Multi-item requests, automated quote generation

#### Pricing & Discounts
- **Purpose**: Dynamic pricing management
- **Key Fields**: `item_price_tier_uuid`, `discount_rule_uuid`, `quantity_ranges`
- **Features**: Volume discounts, rule-based pricing

### Database Schema
The system uses DynamoDB with the following table structure:

- `are-items`: Item catalog
- `are-segments`: Customer segments
- `are-segment-contacts`: Segment-contact relationships
- `are-provider-items`: Provider item catalog
- `are-provider-item-batches`: Batch/lot tracking
- `are-item-price-tiers`: Tiered pricing rules
- `are-discount-rules`: Discount calculation rules
- `are-requests`: RFQ requests
- `are-quotes`: Generated quotes
- `are-quote-items`: Quote line items
- `are-installments`: Payment schedules
- `are-files`: Document attachments

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- AWS Account with DynamoDB access
- AWS CLI configured

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd ai_rfq_engine
```

2. **Install dependencies**
```bash
pip install -e .
```

3. **Install development dependencies**
```bash
pip install -e ".[dev,test]"
```

### Configuration

1. **Environment Setup**
Create a `.env` file with your AWS credentials:
```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
ENDPOINT_ID=your_endpoint_id
EXECUTE_MODE=local_for_all
```

2. **Database Initialization**
The system automatically creates DynamoDB tables when running in local mode.

### Running the Application

#### Local Development
```bash
# Set environment for local development
export EXECUTE_MODE=local_for_all

# Run tests to verify setup
pytest ai_rfq_engine/tests/ -v
```

#### AWS Lambda Deployment
The system is designed for serverless deployment on AWS Lambda. Use the `deploy()` function in `main.py` for deployment configuration.

## 📖 API Documentation

### GraphQL Endpoint
The system exposes a single GraphQL endpoint that handles all operations.

#### Authentication
```http
POST /core/{endpoint_id}/ai_rfq_graphql
Content-Type: application/json
x-api-key: your-api-key
```

### Core Operations

#### Ping Test
```graphql
query {
  ping
}
```

#### Items Management
```graphql
# Create/Update Item
mutation {
  insertUpdateItem(
    itemUuid: "123456789"
    itemType: "raw_material"
    itemName: "Steel Plate"
    itemDescription: "High grade steel plate"
    uom: "kg"
    updatedBy: "user@example.com"
  ) {
    item {
      itemUuid
      itemName
      itemType
    }
  }
}

# Query Items
query {
  itemList(itemType: "raw_material", limit: 10) {
    itemList {
      itemUuid
      itemName
      itemType
      uom
    }
    total
  }
}

# Delete Item
mutation {
  deleteItem(itemUuid: "123456789") {
    ok
  }
}
```

#### Segment Management
```graphql
# Create/Update Segment
mutation {
  insertUpdateSegment(
    segmentUuid: "seg_123"
    segmentName: "Premium Customers"
    segmentDescription: "High value customer segment"
    updatedBy: "admin@company.com"
  ) {
    segment {
      segmentUuid
      segmentName
    }
  }
}

# Query Segments
query {
  segmentList(limit: 10) {
    segmentList {
      segmentUuid
      segmentName
      segmentDescription
    }
    total
  }
}
```

#### Provider Item Management
```graphql
# Create/Update Provider Item
mutation {
  insertUpdateProviderItem(
    providerItemUuid: "pi_123"
    itemUuid: "123456789"
    providerCorpExternalId: "SUPPLIER_001"
    basePricePerUom: 25.50
    itemSpec: "Grade A steel specification"
    updatedBy: "supplier@company.com"
  ) {
    providerItem {
      providerItemUuid
      basePricePerUom
      itemSpec
    }
  }
}
```

#### RFQ Management
```graphql
# Create Request
mutation {
  insertUpdateRequest(
    requestUuid: "req_123"
    email: "buyer@company.com"
    requestTitle: "Q1 Steel Requirements"
    items: [
      {
        itemUuid: "123456789"
        quantity: 1000
        specifications: "Grade A steel"
      }
    ]
    updatedBy: "buyer@company.com"
  ) {
    request {
      requestUuid
      requestTitle
      status
    }
  }
}

# Generate Quote
mutation {
  insertUpdateQuote(
    requestUuid: "req_123"
    quoteUuid: "quote_456"
    providerCorpExternalId: "SUPPLIER_001"
    salesRepEmail: "sales@supplier.com"
    updatedBy: "sales@supplier.com"
  ) {
    quote {
      quoteUuid
      totalQuoteAmount
      status
    }
  }
}

# Add Quote Items
mutation {
  insertUpdateQuoteItem(
    quoteUuid: "quote_456"
    quoteItemUuid: "qi_789"
    providerItemUuid: "pi_123"
    itemUuid: "123456789"
    pricePerUom: 25.50
    qty: 1000
    updatedBy: "sales@supplier.com"
  ) {
    quoteItem {
      quoteItemUuid
      subtotal
      finalSubtotal
    }
  }
}
```

#### Pricing Management
```graphql
# Create Price Tier
mutation {
  insertUpdateItemPriceTier(
    itemUuid: "123456789"
    itemPriceTierUuid: "tier_001"
    quantityGreaterThen: 100
    quantityLessThen: 500
    marginPerUom: 0.15
    updatedBy: "admin@company.com"
  ) {
    itemPriceTier {
      itemPriceTierUuid
      marginPerUom
    }
  }
}

# Create Discount Rule
mutation {
  insertUpdateDiscountRule(
    itemUuid: "123456789"
    discountRuleUuid: "discount_001"
    subtotalGreaterThan: 10000
    maxDiscountPercentage: 0.10
    updatedBy: "admin@company.com"
  ) {
    discountRule {
      discountRuleUuid
      maxDiscountPercentage
    }
  }
}
```

#### Payment Management
```graphql
# Create Installment
mutation {
  insertUpdateInstallment(
    quoteUuid: "quote_456"
    installmentUuid: "inst_001"
    priority: 1
    scheduledDate: "2024-06-01T00:00:00Z"
    installmentAmount: 5000.00
    paymentMethod: "bank_transfer"
    updatedBy: "finance@company.com"
  ) {
    installment {
      installmentUuid
      installmentRatio
      scheduledDate
    }
  }
}
```

#### File Management
```graphql
# Upload File
mutation {
  insertUpdateFile(
    requestUuid: "req_123"
    fileName: "specifications.pdf"
    email: "buyer@company.com"
    fileContent: "base64_encoded_content"
    fileSize: 1024
    fileType: "application/pdf"
    updatedBy: "buyer@company.com"
  ) {
    file {
      fileName
      fileSize
      fileType
    }
  }
}
```

### Advanced Filtering

Most list operations support advanced filtering:

```graphql
# Advanced Item Search
query {
  itemList(
    itemType: "raw_material"
    itemName: "steel"
    uoms: ["kg", "ton"]
    limit: 20
    pageNumber: 0
  ) {
    itemList {
      itemUuid
      itemName
      itemType
      uom
    }
    total
    pageSize
    pageNumber
  }
}

# Date Range Queries
query {
  requestList(
    fromExpiredAt: "2024-01-01T00:00:00Z"
    toExpiredAt: "2024-12-31T23:59:59Z"
    statuses: ["active", "pending"]
    limit: 50
  ) {
    requestList {
      requestUuid
      requestTitle
      status
      expiredAt
    }
    total
  }
}

# Price Range Filtering
query {
  quoteList(
    minTotalQuoteAmount: 1000.0
    maxTotalQuoteAmount: 50000.0
    statuses: ["submitted", "approved"]
  ) {
    quoteList {
      quoteUuid
      totalQuoteAmount
      finalTotalQuoteAmount
      status
    }
    total
  }
}
```

## 🧪 Testing

### Test Suite
The project includes comprehensive tests covering all major functionality.

```bash
# Run all tests
pytest ai_rfq_engine/tests/ -v

# Run specific test categories
pytest ai_rfq_engine/tests/ -m unit -v          # Unit tests only
pytest ai_rfq_engine/tests/ -m integration -v   # Integration tests only

# Run tests for specific functionality
pytest ai_rfq_engine/tests/ -k "item" -v        # Item-related tests

# Run with coverage
pytest ai_rfq_engine/tests/ --cov=ai_rfq_engine --cov-report=html
```

### Test Data
Tests use externalized JSON data in `ai_rfq_engine/tests/test_data.json` for easy maintenance and modification.

### Environment Variables for Testing
```bash
# Run specific test functions
AI_RFQ_TEST_FUNCTION=item pytest ai_rfq_engine/tests/ -v

# Run with specific markers
AI_RFQ_TEST_MARKERS=integration pytest ai_rfq_engine/tests/ -v
```

## 🚀 Deployment

### Local Development Setup

1. **Environment Configuration**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev,test]"
```

2. **Environment Variables**
```env
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
AWS_DEFAULT_REGION=us-east-1
ENDPOINT_ID=your_endpoint_id
EXECUTE_MODE=local_for_all
```

### AWS Lambda Deployment

1. **Package for Deployment**
```bash
# Create deployment package
mkdir deployment
cp -r ai_rfq_engine deployment/
cp requirements.txt deployment/
cd deployment

# Install dependencies
pip install -r requirements.txt -t .

# Create ZIP file
zip -r ai_rfq_engine.zip .
```

2. **Lambda Function Creation**
```bash
# Create Lambda function
aws lambda create-function \
    --function-name ai-rfq-engine \
    --runtime python3.9 \
    --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
    --handler ai_rfq_engine.main.lambda_handler \
    --zip-file fileb://ai_rfq_engine.zip \
    --timeout 300 \
    --memory-size 512
```

3. **Environment Variables**
```bash
aws lambda update-function-configuration \
    --function-name ai-rfq-engine \
    --environment Variables='{
        "ENDPOINT_ID":"your_endpoint_id",
        "SOURCE_EMAIL":"noreply@yourcompany.com",
        "EXECUTE_MODE":"production"
    }'
```

### Database Setup

The system automatically creates DynamoDB tables when running in local mode. For production:

1. **Enable Point-in-Time Recovery**
```bash
aws dynamodb put-backup-policy \
    --table-name are-items \
    --backup-policy PointInTimeRecoveryEnabled=true
```

2. **Create Backup**
```bash
aws dynamodb create-backup \
    --table-name are-items \
    --backup-name are-items-backup-$(date +%Y%m%d)
```

### Monitoring

1. **CloudWatch Logs**
```bash
aws logs put-retention-policy \
    --log-group-name /aws/lambda/ai-rfq-engine \
    --retention-in-days 30
```

2. **Health Check**
```graphql
query {
  ping  # Returns current timestamp if system is healthy
}
```

## 🔧 Development

### Code Quality
The project uses several tools to maintain code quality:

```bash
# Code formatting
black ai_rfq_engine/

# Linting
flake8 ai_rfq_engine/

# Type checking
mypy ai_rfq_engine/
```

### Adding New Features

1. **Models**: Add new data models in `ai_rfq_engine/models/`
2. **Types**: Define GraphQL types in `ai_rfq_engine/types/`
3. **Queries**: Add query resolvers in `ai_rfq_engine/queries/`
4. **Mutations**: Add mutation resolvers in `ai_rfq_engine/mutations/`
5. **Tests**: Add corresponding tests in `ai_rfq_engine/tests/`

### Development Workflow

1. **Create Feature Branch**
```bash
git checkout -b feature/your-feature-name
```

2. **Make Changes**
- Write code following style guidelines
- Add tests for new functionality
- Update documentation as needed

3. **Test Changes**
```bash
pytest ai_rfq_engine/tests/ -v
black ai_rfq_engine/
flake8 ai_rfq_engine/
```

4. **Commit and Push**
```bash
git add .
git commit -m "feat: add new feature description"
git push origin feature/your-feature-name
```

## 🤝 Contributing

### Development Guidelines
- Follow PEP 8 style guidelines
- Add tests for new functionality
- Update documentation for API changes
- Use type hints where appropriate

### Code Style

```python
# Variables and functions: snake_case
user_name = "john_doe"
def calculate_total_price():
    pass

# Classes: PascalCase
class ItemModel:
    pass

# Constants: UPPER_SNAKE_CASE
MAX_RETRY_ATTEMPTS = 3
```

### Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Bug Reports

When reporting bugs, please include:
- Clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)

## 🔒 Security

### API Key Management
- Generate strong API keys using `openssl rand -hex 32`
- Store keys securely in AWS Secrets Manager
- Rotate keys regularly

### IAM Permissions
Create minimal privilege IAM role for Lambda:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan"
            ],
            "Resource": "arn:aws:dynamodb:*:*:table/are-*"
        }
    ]
}
```

### Data Protection
- Enable DynamoDB encryption at rest
- Use HTTPS only for API endpoints
- Implement comprehensive input validation

## 🆘 Troubleshooting

### Common Issues

#### Table Creation Failures
```python
# Check AWS credentials and permissions
import boto3
dynamodb = boto3.client('dynamodb')
try:
    response = dynamodb.list_tables()
    print("DynamoDB access successful")
except Exception as e:
    print(f"DynamoDB access failed: {e}")
```

#### Lambda Timeout Issues
- Increase timeout in Lambda configuration
- Optimize query performance
- Use pagination for large datasets

#### Memory Issues
- Increase memory allocation
- Optimize data processing
- Use streaming for large responses

### Debug Mode
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or set environment variable
import os
os.environ['LOG_LEVEL'] = 'DEBUG'
```

### Performance Optimization
- Use appropriate DynamoDB indexes
- Implement pagination for large datasets
- Cache frequently accessed data
- Process data in chunks for large operations

## 📚 API Reference

### Postman Collection
A comprehensive Postman collection is available at `ai_rfq_postman_collection.json` with examples for all API operations.

### Error Handling
The API returns standard GraphQL errors with additional context:

```json
{
  "errors": [
    {
      "message": "Item with UUID '123' does not exist",
      "locations": [{"line": 2, "column": 3}],
      "path": ["insertUpdateProviderItem"]
    }
  ],
  "data": null
}
```

### Rate Limiting
- 1000 requests per minute per API key
- Burst limit of 100 requests per second

### Data Types

#### Custom Scalars
- **DateTime**: ISO 8601 formatted date-time strings
- **JSON**: Arbitrary JSON objects for flexible data storage

#### Enums
- **Item Types**: `raw_material`, `finished_good`, `service`, `component`
- **Status**: `initial`, `draft`, `submitted`, `under_review`, `approved`, `rejected`, `expired`
- **Payment Methods**: `credit_card`, `bank_transfer`, `check`, `net_terms`

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔄 Changelog

### Version 0.0.1 - Initial Release

#### Added
- **Core Features**: Complete GraphQL API with queries and mutations
- **Item Management**: Full CRUD operations for product/service catalog
- **Provider Management**: Supplier onboarding and item catalog management
- **RFQ Processing**: Request for Quote creation and management
- **Quote Generation**: Automated quote creation with line items
- **Pricing Engine**: Tiered pricing and discount rule management
- **Payment Scheduling**: Installment planning and management
- **File Management**: Document attachment system for RFQ processes

#### Technical Details
- **Database**: DynamoDB integration with auto table creation
- **Authentication**: API key-based authentication
- **Testing**: Comprehensive test suite with parametrized data
- **Deployment**: AWS Lambda deployment configuration
- **Monitoring**: CloudWatch integration and health checks

#### Dependencies
- `graphene>=3.0`: GraphQL framework
- `pendulum>=2.0`: Date/time handling
- `tenacity>=8.0`: Retry mechanisms
- `SilvaEngine-DynamoDB-Base`: Custom DynamoDB framework
- `SilvaEngine-Utility`: Utility functions

## 🆘 Support

### Documentation
- Complete API examples in this README
- Test data documentation in `ai_rfq_engine/tests/README_TEST_DATA.md`
- Postman collection for API testing

### Getting Help
1. Check this documentation for common solutions
2. Review the test examples for usage patterns
3. Use the Postman collection for API testing
4. Check GitHub Issues for known problems

### Contact
- **Author**: Idea Bosque
- **Email**: ideabosque@gmail.com
- **Issues**: Use GitHub Issues for bug reports and feature requests

---

**Built with ❤️ using Python and AWS**
# Modern ERP System

A modern Django-based ERP system inspired by iDempiere's proven architecture but built with modern technologies and US GAAP best practices.

## 🚀 Key Features

- **Modern Architecture**: Built with Django 4.2, PostgreSQL, and Django REST Framework
- **iDempiere Inspired**: Based on the proven architecture of iDempiere but modernized
- **US GAAP Compliant**: Implements US accounting standards and best practices
- **Double-Entry Bookkeeping**: Full accounting system with journal entries
- **Multi-Organization**: Support for multiple companies/organizations
- **Comprehensive Business Partner Management**: Customers, vendors, employees
- **Modern Security**: JWT authentication, proper user management
- **API-First**: RESTful APIs with automatic documentation
- **Admin Interface**: Rich Django admin interface for all modules

## 📋 Core Modules

### Core Module
- **User Management**: Extended Django user model with ERP-specific fields
- **Organizations**: Multi-company support with hierarchical structure
- **Business Partners**: Unified customer/vendor/employee management
- **Currencies**: Multi-currency support
- **Number Sequences**: Automatic document numbering
- **Units of Measure**: Product measurement units

### Accounting Module
- **Chart of Accounts**: Hierarchical account structure
- **Account Types**: US GAAP account classifications
- **Fiscal Years & Periods**: Accounting period management
- **General Ledger**: Double-entry journal system
- **Tax Management**: Sales tax, VAT, and US tax compliance
- **Budget Control**: Budget planning and variance analysis

## 🛠 Technology Stack

- **Backend**: Django 4.2 with Python 3.8+
- **Database**: PostgreSQL 12+
- **API**: Django REST Framework with OpenAPI documentation
- **Authentication**: JWT tokens + session authentication
- **Money Handling**: Django Money for proper currency support
- **Admin**: Enhanced Django admin interface
- **Frontend Ready**: CORS enabled for modern frontend frameworks

## 🔧 Installation & Setup

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- Git

### Quick Start

1. **Activate the virtual environment**:
   ```bash
   cd /opt/idempiere-server/modern-erp
   source venv/bin/activate
   ```

2. **Run the development server**:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

3. **Access the system**:
   - Admin Interface: http://your-server:8000/admin/
   - Username: `admin`
   - Password: `admin123`

### Database Configuration

The system uses PostgreSQL with the following configuration:
- Database: `modern_erp`
- User: `django_user`
- Password: `django_pass`

## 📊 Data Models

### Core Models
- **User**: Extended Django user with ERP fields
- **Organization**: Company/organization master
- **BusinessPartner**: Customer/vendor/employee unified model
- **Currency**: Currency master data
- **UnitOfMeasure**: Measurement units
- **NumberSequence**: Document numbering

### Accounting Models
- **Account**: General ledger accounts with US GAAP support
- **AccountType**: Account classifications (Asset, Liability, etc.)
- **FiscalYear/Period**: Accounting periods
- **Journal/JournalLine**: Double-entry bookkeeping
- **Tax**: Tax definitions with US compliance features

## 🎯 Key Improvements Over iDempiere

1. **Modern Technology Stack**: Latest Django, Python, and web technologies
2. **API-First Design**: RESTful APIs for all functionality
3. **Better UX**: Modern admin interface, responsive design
4. **US GAAP Focus**: Built specifically for US accounting standards
5. **Cloud Ready**: Designed for modern cloud deployments
6. **Developer Friendly**: Clean code, proper documentation, testing framework

## 🔐 Security Features

- JWT token authentication
- Session-based authentication fallback
- Proper user permission system
- CORS configuration for frontend integration
- SQL injection protection (Django ORM)
- XSS protection
- CSRF protection

## 📈 US GAAP Compliance

- Current vs Non-current asset classification
- Proper revenue recognition framework
- 1099 vendor tracking
- Standard account types (Assets, Liabilities, Equity, Revenue, Expenses)
- Financial statement presentation flags
- Tax jurisdiction tracking

## 🚀 Next Steps

1. **Sales Module**: Orders, invoices, shipments
2. **Purchasing Module**: Purchase orders, receipts, vendor bills
3. **Inventory Module**: Product catalog, stock management
4. **Reporting**: Financial statements, management reports
5. **Frontend Application**: React/Vue.js modern web interface
6. **Mobile App**: iOS/Android applications
7. **API Documentation**: Interactive API docs with Swagger
8. **Data Migration**: Tools to migrate from iDempiere

## 🤝 Contributing

This is a modern replacement for iDempiere with focus on:
- Clean, maintainable code
- Modern development practices
- US business requirements
- Cloud-native architecture
- API-first design

## 📞 Support

For support and questions:
- Check the Django admin interface at `/admin/`
- Review the API documentation at `/api/schema/swagger-ui/`
- Database can be accessed via standard PostgreSQL tools

---

**Built with ❤️ using Django and modern web technologies**
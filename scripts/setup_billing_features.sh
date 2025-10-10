#!/bin/bash

# Setup script for Billing, Usage, and Security features
# This script helps set up the new features

set -e

echo "======================================"
echo "VoiceAgent SaaS - Feature Setup Script"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in the project root
if [ ! -f "backend/requirements.txt" ]; then
    echo -e "${RED}Error: This script must be run from the project root directory${NC}"
    exit 1
fi

echo -e "${GREEN}Step 1: Installing Backend Dependencies${NC}"
cd backend
pip install stripe==10.11.0
echo -e "${GREEN}✓ Stripe installed${NC}"
echo ""

echo -e "${GREEN}Step 2: Checking Database Configuration${NC}"
if [ -z "$DATABASE_URL" ]; then
    echo -e "${YELLOW}Warning: DATABASE_URL environment variable not set${NC}"
    echo "Please set it in your .env file"
else
    echo -e "${GREEN}✓ DATABASE_URL configured${NC}"
fi
echo ""

echo -e "${GREEN}Step 3: Database Migration${NC}"
echo "Migration file location: database/migrations_billing_usage_security.sql"
echo ""
echo "Please run the migration using one of these methods:"
echo ""
echo "For PostgreSQL:"
echo "  psql -U postgres -d voiceagent -f database/migrations_billing_usage_security.sql"
echo ""
echo "For Supabase:"
echo "  1. Go to your Supabase project"
echo "  2. Navigate to SQL Editor"
echo "  3. Copy and paste the migration file contents"
echo "  4. Execute the migration"
echo ""
read -p "Have you run the database migration? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Please run the migration before continuing${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Database migration confirmed${NC}"
echo ""

echo -e "${GREEN}Step 4: Stripe Configuration (Optional)${NC}"
echo "To enable billing features, add these to your .env file:"
echo ""
echo "STRIPE_API_KEY=sk_test_..."
echo "STRIPE_WEBHOOK_SECRET=whsec_..."
echo "STRIPE_BASIC_PRICE_ID=price_..."
echo "STRIPE_PRO_PRICE_ID=price_..."
echo "STRIPE_ENTERPRISE_PRICE_ID=price_..."
echo ""
read -p "Have you configured Stripe? (y/n/skip) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}✓ Stripe configured${NC}"
elif [[ $REPLY =~ ^[Ss]$ ]]; then
    echo -e "${YELLOW}⚠ Skipped Stripe configuration - billing features will be disabled${NC}"
else
    echo -e "${YELLOW}⚠ Stripe not configured - billing features will be disabled${NC}"
fi
echo ""

echo -e "${GREEN}Step 5: Frontend Dependencies${NC}"
cd ../frontend
if command -v yarn &> /dev/null; then
    echo "Checking for missing dependencies..."
    yarn install
    echo -e "${GREEN}✓ Frontend dependencies checked${NC}"
elif command -v npm &> /dev/null; then
    echo "Checking for missing dependencies..."
    npm install
    echo -e "${GREEN}✓ Frontend dependencies checked${NC}"
else
    echo -e "${YELLOW}⚠ Neither yarn nor npm found. Please install dependencies manually${NC}"
fi
echo ""

echo -e "${GREEN}Step 6: Verification${NC}"
cd ..
echo "Checking files..."

# Check backend files
backend_files=(
    "backend/app/models/billing.py"
    "backend/app/models/security.py"
    "backend/app/api/billing.py"
    "backend/app/api/usage.py"
    "backend/app/api/security.py"
)

for file in "${backend_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file (missing)"
    fi
done

# Check frontend files
frontend_files=(
    "frontend/src/pages/BillingPage.tsx"
    "frontend/src/pages/UsagePage.tsx"
    "frontend/src/pages/SecurityPage.tsx"
)

for file in "${frontend_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file (missing)"
    fi
done

echo ""
echo -e "${GREEN}Step 7: Testing Setup${NC}"
echo ""
echo "To test the setup:"
echo ""
echo "1. Start the backend:"
echo "   cd backend"
echo "   uvicorn app.main:app --reload"
echo ""
echo "2. Start the frontend:"
echo "   cd frontend"
echo "   yarn dev  # or npm run dev"
echo ""
echo "3. Access the application:"
echo "   http://localhost:5173"
echo ""
echo "4. Test the new features:"
echo "   - Navigate to /dashboard/billing"
echo "   - Navigate to /dashboard/usage"
echo "   - Navigate to /dashboard/security"
echo ""

echo -e "${GREEN}======================================"
echo "Setup Complete!"
echo "======================================${NC}"
echo ""
echo "Documentation: BILLING_USAGE_SECURITY_GUIDE.md"
echo "API Docs: http://localhost:8000/api/docs"
echo ""
echo "Next steps:"
echo "1. Review the documentation"
echo "2. Configure Stripe (if not done)"
echo "3. Test the features"
echo "4. Deploy to production"
echo ""
echo -e "${GREEN}Happy coding! 🚀${NC}"


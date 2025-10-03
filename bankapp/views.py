from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework import status
from datetime import date
from .models import Customer, Bank, LoanRule, CustomerInterest ,Product, User, ManagedCard, CompanyCategory, Company, SalaryCriteria
from .serializers import CustomerSerializer, BankSerializer, LoanRuleSerializer, CustomerInterestSerializer , AdminLoginSerializer , ProductSerializer , UserSerializer, ManagedCardSerializer , CompanyCategorySerializer, CompanySerializer , SalaryCriteriaSerializer

# 🔹 Admin Login API
@api_view(["POST"])
def admin_login(request):
    serializer = AdminLoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data["user"]
        return Response(
            {"message": "Admin login successful", "email": user.email},
            status=status.HTTP_200_OK
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# 🔹 Create new admin (limit max 3 admins)
@api_view(["POST"])
def create_admin(request):
    if User.objects.filter(role="admin").count() >= 3:
        return Response({"error": "Maximum 3 admins allowed"}, status=status.HTTP_400_BAD_REQUEST)

    data = request.data
    data["role"] = "admin"
    serializer = UserSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# 🔹 Update admin (email or password)
@api_view(["PUT"])
def update_admin(request, pk):
    try:
        admin = User.objects.get(pk=pk, role="admin")
    except User.DoesNotExist:
        return Response({"error": "Admin not found"}, status=status.HTTP_404_NOT_FOUND)

    old_password = request.data.get("old_password")
    new_password = request.data.get("new_password")

    # Password update (requires old password)
    if old_password and new_password:
        if not admin.check_password(old_password):
            return Response({"error": "Old password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)
        admin.set_password(new_password)
        admin.save()
        return Response({"message": "Password updated successfully"}, status=status.HTTP_200_OK)

    # Other updates (like email)
    serializer = UserSerializer(admin, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(["POST"])
def customer_create_or_eligible_banks(request):
    try:
        data = request.data
        email = data.get("email")
        phone = data.get("phone")

        # Check if customer exists (by email OR phone)
        customer = Customer.objects.filter(email=email).first() or Customer.objects.filter(phone=phone).first()
        action = "updated" if customer else "created"

        # Create or Update customer
        if customer:
            serializer = CustomerSerializer(customer, data=data, partial=True)
        else:
            serializer = CustomerSerializer(data=data)

        if serializer.is_valid():
            customer = serializer.save()

            # 🔹 Annual Income
            if customer.salary:
                customer.annualIncome = float(customer.salary) * 12
                customer.save()

            # 🔹 Calculate Age
            age = None
            if customer.dob:
                today = date.today()
                age = today.year - customer.dob.year - (
                    (today.month, today.day) < (customer.dob.month, customer.dob.day)
                )

            # 🔹 Eligible Banks
            eligible_banks = []
            for bank in Bank.objects.filter(pincode=customer.pincode):
                for rule in LoanRule.objects.filter(bank=bank):
                    if (
                        customer.salary
                        and float(customer.salary) >= float(rule.min_salary)
                        and customer.employment_type
                        and customer.employment_type.lower().strip() == rule.job_type.lower().strip()
                        and age is not None and rule.min_age <= age <= rule.max_age
                    ):
                        eligible_banks.append({
                            "bank_name": bank.bank_name,
                            "tenure": rule.tenure,
                            "min_rate": rule.min_rate,
                            "max_rate": rule.max_rate,
                            "min_salary_required": float(rule.min_salary),
                            "job_type": rule.job_type,
                            "age_limit": f"{rule.min_age}-{rule.max_age}",
                            "max_loan_amount": f"Up to ₹{float(customer.salary) * 5:,.0f}"
                        })

            # 🔹 Build response
            customer_data = CustomerSerializer(customer).data
            customer_data["age"] = age

            return Response({
                "status": action,  # "created" or "updated"
                "message": f"Customer {action} successfully",
                "customer": customer_data,
                "eligible_banks": eligible_banks
            }, status=status.HTTP_201_CREATED if action == "created" else status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# List all banks OR create new bank
@api_view(['GET', 'POST'])
def bank_list_create(request):
    if request.method == 'GET':
        banks = Bank.objects.all()
        serializer = BankSerializer(banks, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = BankSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        # Return validation errors (e.g., duplicate bank_name or invalid pincodes)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -------------------- Retrieve / Update / Delete Bank --------------------
@api_view(['GET', 'PUT', 'DELETE'])
def bank_detail(request, pk):
    try:
        bank = Bank.objects.get(pk=pk)
    except Bank.DoesNotExist:
        return Response({"error": "Bank not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = BankSerializer(bank)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = BankSerializer(bank, data=request.data, partial=True)  # allow partial update
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        # Return validation errors (e.g., duplicate bank_name or invalid pincodes)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        bank.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
# Filter banks by a given pincode
@api_view(['GET'])
def banks_by_pincodes(request, pincodes):
    """
    Filter banks by comma-separated pincodes in URL.
    Example: /v1/api/banks/pincode/123456,110002/
    """
    pincode_list = [p.strip() for p in pincodes.split(',') if p.strip()]
    
    valid_pins = []
    invalid_pins = []

    serializer_instance = BankSerializer()  # instance for calling validate_pincode

    # Validate each pincode individually
    for pin in pincode_list:
        try:
            serializer_instance.validate_pincode(pin)
            valid_pins.append(pin)
        except serializers.ValidationError:
            invalid_pins.append(pin)

    # If no valid pincodes, return empty list
    if not valid_pins:
        return Response({
            "banks": [],
            "ignored_invalid_pincodes": invalid_pins
        }, status=status.HTTP_400_BAD_REQUEST)

    # Fetch banks for all valid pincodes
    banks = Bank.objects.none()
    for pin in valid_pins:
        banks |= Bank.objects.filter(pincode__regex=fr'(^|,){pin}(,|$)')

    banks = banks.distinct()
    serializer = BankSerializer(banks, many=True)

    response_data = {"banks": serializer.data}
    if invalid_pins:
        response_data["ignored_invalid_pincodes"] = invalid_pins

    return Response(response_data)


# List, Create, Retrieve, Update, Delete Loan Rules
@api_view(['GET', 'POST', 'PUT', 'DELETE'])
def loanrule_list(request, pk=None):
    # -------------------- GET --------------------
    if request.method == 'GET':
        if pk:  # Get single loan rule
            try:
                loanrule = LoanRule.objects.get(pk=pk)
            except LoanRule.DoesNotExist:
                return Response({"error": "Loan rule not found"}, status=status.HTTP_404_NOT_FOUND)
            serializer = LoanRuleSerializer(loanrule)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Get list of loan rules (optionally filter by bank_id)
        bank_id = request.GET.get('bank_id')
        if bank_id:
            loanrules = LoanRule.objects.filter(bank_id=bank_id)
        else:
            loanrules = LoanRule.objects.all()
        serializer = LoanRuleSerializer(loanrules, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # -------------------- POST --------------------
    elif request.method == 'POST':
        bank_id = request.data.get("bank")
        job_type = request.data.get("job_type")

        # Check for duplicate rule for the same bank & job type
        if LoanRule.objects.filter(bank_id=bank_id, job_type__iexact=job_type).exists():
            return Response(
                {"error": f"A loan rule already exists for bank ID {bank_id} with job type '{job_type}'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = LoanRuleSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # -------------------- PUT --------------------
    elif request.method == 'PUT':
        if not pk:
            return Response({"error": "Loan rule ID required in URL"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            loanrule = LoanRule.objects.get(pk=pk)
        except LoanRule.DoesNotExist:
            return Response({"error": "Loan rule not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = LoanRuleSerializer(loanrule, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # -------------------- DELETE --------------------
    elif request.method == 'DELETE':
        if not pk:
            return Response({"error": "Loan rule ID required in URL"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            loanrule = LoanRule.objects.get(pk=pk)
            loanrule.delete()
            return Response({"message": "Loan rule deleted successfully"}, status=status.HTTP_200_OK)
        except LoanRule.DoesNotExist:
            return Response({"error": "Loan rule not found"}, status=status.HTTP_404_NOT_FOUND)

# Get all loan rules for a specific bank
@api_view(['GET'])
def loanrules_by_bank(request, bank_id):
    try:
        bank = Bank.objects.get(pk=bank_id)
    except Bank.DoesNotExist:
        return Response({"error": "Bank not found"}, status=status.HTTP_404_NOT_FOUND)
    
    loanrules = LoanRule.objects.filter(bank__id=bank_id)
    serializer = LoanRuleSerializer(loanrules, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET", "POST"])
def customer_interest_list_create(request):
    if request.method == "GET":
        interests = CustomerInterest.objects.all()
        serializer = CustomerInterestSerializer(interests, many=True)
        return Response(serializer.data)

    elif request.method == "POST":
        serializer = CustomerInterestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def customer_interests_by_customer(request, customer_id):
    interests = CustomerInterest.objects.filter(customer_id=customer_id)
    serializer = CustomerInterestSerializer(interests, many=True)
    return Response(serializer.data) 
@api_view(['GET', 'POST', 'PUT', 'DELETE'])
def product_list(request, pk=None):
    # -------------------- GET --------------------
    if request.method == 'GET':
        if pk:
            try:
                product = Product.objects.get(pk=pk)
                serializer = ProductSerializer(product)
                return Response(serializer.data)
            except Product.DoesNotExist:
                return Response({"error": "Product not found"}, status=404)
        else:
            products = Product.objects.all()
            serializer = ProductSerializer(products, many=True)
            return Response(serializer.data)

    # -------------------- POST --------------------
    elif request.method == 'POST':
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            product = serializer.save()
            return Response(ProductSerializer(product).data, status=201)
        return Response(serializer.errors, status=400)

    # -------------------- PUT --------------------
    elif request.method == 'PUT':
        if not pk:
            return Response({"error": "Product ID required"}, status=400)
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=404)

        serializer = ProductSerializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            product = serializer.save()

            # Handle SalaryCriteria update
            categories_input = request.data.get("categories", [])

            # Convert dict to list if necessary
            if categories_input and isinstance(categories_input, dict):
                categories_input = [{"category_name": k, "min_salary": v} for k, v in categories_input.items()]

            existing_sc = SalaryCriteria.objects.filter(product=product)

            # Update or create new salary criteria
            for item in categories_input:
                category_name = item.get("category_name")
                salary = item.get("min_salary")
                if category_name and salary and float(salary) > 0:
                    category, _ = CompanyCategory.objects.get_or_create(category_name=category_name)
                    sc, created = SalaryCriteria.objects.get_or_create(product=product, category=category)
                    sc.min_salary = salary
                    sc.save()
            
            # Optionally: Remove categories that are not sent in update
            sent_category_names = [item.get("category_name") for item in categories_input]
            SalaryCriteria.objects.filter(product=product).exclude(category__category_name__in=sent_category_names).delete()

            return Response(ProductSerializer(product).data)

        return Response(serializer.errors, status=400)

    # -------------------- DELETE --------------------
    elif request.method == 'DELETE':
        if not pk:
            return Response({"error": "Product ID required"}, status=400)
        try:
            product = Product.objects.get(pk=pk)
            product.delete()
            return Response({"message": "Product deleted"})
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=404)

        
@api_view(["GET"])
def get_products_by_bank(request, bank_id):
    products = Product.objects.filter(bank_id=bank_id)
    if not products.exists():
        return Response({"error": "No products found for this bank"}, status=status.HTTP_404_NOT_FOUND)
    serializer = ProductSerializer(products, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)        

@api_view(['GET', 'POST'])
def managed_card_list_create(request):
    if request.method == 'GET':
        cards = ManagedCard.objects.all()
        serializer = ManagedCardSerializer(cards, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = ManagedCardSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
# Retrieve + Update + Delete
@api_view(['GET', 'PUT', 'DELETE'])
def managed_card_detail(request, pk):
    try:
        card = ManagedCard.objects.get(pk=pk)
    except ManagedCard.DoesNotExist:
        return Response({"error": "Card not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = ManagedCardSerializer(card)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = ManagedCardSerializer(card, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        card.delete()
        return Response(status=status.HTTP_200_OK)

@api_view(['GET', 'POST'])
def company_category_list_create(request):
    if request.method == 'GET':
        categories = CompanyCategory.objects.all()
        serializer = CompanyCategorySerializer(categories, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = CompanyCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Retrieve, Update, Delete single category
@api_view(['GET', 'PUT', 'DELETE'])
def company_category_detail(request, pk):
    try:
        category = CompanyCategory.objects.get(pk=pk)
    except CompanyCategory.DoesNotExist:
        return Response({"error": "Category not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = CompanyCategorySerializer(category)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = CompanyCategorySerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        category.delete()
        return Response(status=status.HTTP_200_OK)        
    
# List + Create
@api_view(['GET', 'POST'])
def company_list_create(request):
    if request.method == 'GET':
        companies = Company.objects.all()
        serializer = CompanySerializer(companies, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = CompanySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Retrieve + Update + Delete
@api_view(['GET', 'PUT', 'DELETE'])
def company_detail(request, pk):
    try:
        company = Company.objects.get(pk=pk)
    except Company.DoesNotExist:
        return Response({"error": "Company not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = CompanySerializer(company)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = CompanySerializer(company, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        company.delete()
        return Response(status=status.HTTP_200_OK)
    
@api_view(['GET', 'POST'])
def salary_criteria_list_create(request):
    if request.method == 'GET':
        criteria = SalaryCriteria.objects.all()
        serializer = SalaryCriteriaSerializer(criteria, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = SalaryCriteriaSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
def salary_criteria_detail(request, pk):
    try:
        criteria = SalaryCriteria.objects.get(pk=pk)
    except SalaryCriteria.DoesNotExist:
        return Response({"error": "Salary Criteria not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = SalaryCriteriaSerializer(criteria)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = SalaryCriteriaSerializer(criteria, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        criteria.delete()
        return Response(status=status.HTTP_200_OK)    
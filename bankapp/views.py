from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework import status
from datetime import date
from django.utils import timezone
from .models import Customer, Bank, CustomerInterest ,Product, User, ManagedCard, CompanyCategory, Company, SalaryCriteria
from .serializers import CustomerSerializer, BankSerializer, CustomerInterestSerializer , AdminLoginSerializer , ProductSerializer , UserSerializer, ManagedCardSerializer , CompanyCategorySerializer, CompanySerializer , SalaryCriteriaSerializer

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
    """
    Check loan eligibility for a customer based on:
    - Company category and salary criteria
    - Age limits from product
    - Bank coverage by pincode
    Restriction: A customer can check eligibility only once per day.
    """
    try:
        data = request.data

        # Step 1: Validate Required Fields
        required_fields = ["full_name", "email", "phone", "dob", "salary", "pincode"]
        missing_fields = [field for field in required_fields if not data.get(field)]

        if missing_fields:
            return Response({
                "status": "error",
                "message": f"Missing required fields: {', '.join(missing_fields)}"
            }, status=status.HTTP_400_BAD_REQUEST)

        email = data.get("email")
        phone = data.get("phone")
        company_name = data.get("companyName", "").strip()
        applicant_salary = float(data.get("salary", 0))
        applicant_pincode = str(data.get("pincode", "")).strip()

        # Step 2: Check if customer already exists
        customer = Customer.objects.filter(email=email).first() or Customer.objects.filter(phone=phone).first()

        # ✅ Restrict eligibility check once per day
        if customer:
            if customer.last_eligibility_check == date.today():
                return Response({
                    "status": "restricted",
                    "message": "You have already checked your eligibility today. Please try again tomorrow.",
                    "last_checked_on": customer.last_eligibility_check
                }, status=status.HTTP_403_FORBIDDEN)
            else:
                # Do not update existing customer details — just restrict modification
                return Response({
                    "status": "restricted",
                    "message": "Your data already exists and cannot be updated today. Try again tomorrow."
                }, status=status.HTTP_403_FORBIDDEN)

        # Step 3: Create a new customer
        serializer = CustomerSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        customer = serializer.save()

        # Calculate Annual Income
        if customer.salary:
            customer.annualIncome = float(customer.salary) * 12
            customer.save()

        # Step 4: Calculate Age from DOB
        if not customer.dob:
            return Response({
                "status": "error",
                "message": "Date of birth is required to calculate age"
            }, status=status.HTTP_400_BAD_REQUEST)

        today = date.today()
        age = today.year - customer.dob.year - (
            (today.month, today.day) < (customer.dob.month, customer.dob.day)
        )

        # Step 5: Determine Company Category
        company_category = None
        if company_name:
            try:
                company_obj = Company.objects.filter(company_name__iexact=company_name).first()
                if company_obj:
                    company_category = company_obj.category
                else:
                    company_category, _ = CompanyCategory.objects.get_or_create(category_name="UNLISTED")
            except Exception:
                company_category, _ = CompanyCategory.objects.get_or_create(category_name="UNLISTED")
        else:
            company_category, _ = CompanyCategory.objects.get_or_create(category_name="UNLISTED")

        # Step 6: Check Eligibility
        eligible_banks = []
        ineligibility_reasons = []

        for bank in Bank.objects.all():
            bank_pins = bank.get_pincode_list()
            if applicant_pincode not in bank_pins:
                ineligibility_reasons.append({
                    "bank_name": bank.bank_name,
                    "reason": "Bank not available in your area (pincode not served)"
                })
                continue

            for product in Product.objects.filter(bank=bank):
                # Check age range
                if product.min_age and product.max_age:
                    if not (product.min_age <= age <= product.max_age):
                        ineligibility_reasons.append({
                            "bank_name": bank.bank_name,
                            "product": product.product_title,
                            "reason": f"Age {age} not in range {product.min_age}-{product.max_age}"
                        })
                        continue

                salary_criteria_list = SalaryCriteria.objects.filter(
                    product=product, category=company_category
                )
                if not salary_criteria_list.exists():
                    ineligibility_reasons.append({
                        "bank_name": bank.bank_name,
                        "product": product.product_title,
                        "reason": f"No salary criteria defined for category '{company_category.category_name}'"
                    })
                    continue

                matched_criteria = None
                salary_ok = False
                for criteria in salary_criteria_list:
                    if applicant_salary >= float(criteria.min_salary):
                        salary_ok = True
                        matched_criteria = criteria
                        break

                if not salary_ok:
                    min_required = float(salary_criteria_list.first().min_salary)
                    ineligibility_reasons.append({
                        "bank_name": bank.bank_name,
                        "product": product.product_title,
                        "reason": f"Salary below minimum ₹{min_required:,.0f} for {company_category.category_name}"
                    })
                    continue

                # ✅ Eligible bank
                eligible_banks.append({
                    "bank_id": bank.id,
                    "bank_name": bank.bank_name,
                    "product_id": product.id,
                    "product_name": product.product_title,
                    "eligibility_status": "Eligible",
                    "company_category": company_category.category_name,
                    "min_salary_required": float(matched_criteria.min_salary),
                    "applicant_salary": applicant_salary,
                    "age_requirement": f"{product.min_age}-{product.max_age} years" if product.min_age and product.max_age else "N/A",
                    "applicant_age": age,
                    "tenure_range": f"{product.min_tenure}-{product.max_tenure} months" if product.min_tenure and product.max_tenure else "N/A",
                    "roi_range": f"{product.min_roi}%-{product.max_roi}%" if product.min_roi and product.max_roi else "N/A",
                    "loan_amount_range": {
                        "min": float(product.min_loan_amount) if product.min_loan_amount else 0,
                        "max": float(product.max_loan_amount) if product.max_loan_amount else applicant_salary * 5
                    },
                    "foir_details": product.foir_details or "N/A",
                    "estimated_max_loan": float(product.max_loan_amount) if product.max_loan_amount else applicant_salary * 5
                })

        # Step 7: Update last eligibility check date
        customer.last_eligibility_check = date.today()
        customer.save()

        # Step 8: Build Final Response
        customer_data = CustomerSerializer(customer).data
        customer_data["age"] = age
        customer_data["company_category"] = company_category.category_name if company_category else "N/A"

        overall_status = "Eligible" if eligible_banks else "Not Eligible"

        response_data = {
            "status": "created",
            "message": "Customer created and eligibility checked successfully",
            "eligibility_status": overall_status,
            "customer": customer_data,
            "eligible_banks_count": len(eligible_banks),
            "eligible_banks": eligible_banks
        }

        if not eligible_banks and ineligibility_reasons:
            response_data["ineligibility_reasons"] = ineligibility_reasons[:5]

        return Response(response_data, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({
            "status": "error",
            "message": "An error occurred while checking eligibility",
            "error": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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


@api_view(["GET", "POST"])
def customer_interest_list_create(request):
    """
    GET  → List all customer interests with full linked details
    POST → Create a new customer interest (with customer, bank, and optional product)
    """

    if request.method == "GET":
        # Fetch all interests with related customer, bank, product data
        interests = CustomerInterest.objects.select_related("customer", "bank", "product").all().order_by('-created_at')
        serializer = CustomerInterestSerializer(interests, many=True)
        return Response({
            "status": "success",
            "message": "All customer interests fetched successfully.",
            "count": len(serializer.data),
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    elif request.method == "POST":
        serializer = CustomerInterestSerializer(data=request.data)
        if serializer.is_valid():
            interest = serializer.save()
            return Response({
                "status": "success",
                "message": "Customer interest created successfully.",
                "data": CustomerInterestSerializer(interest).data
            }, status=status.HTTP_201_CREATED)
        return Response({
            "status": "error",
            "message": "Invalid data provided.",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)



@api_view(["GET"])
def customer_interests_by_customer(request, customer_id):
    """
    GET → Fetch all interests for a specific customer
    """
    interests = CustomerInterest.objects.select_related("customer", "bank", "product").filter(customer_id=customer_id)
    serializer = CustomerInterestSerializer(interests, many=True)
    return Response(serializer.data) 


@api_view(['GET', 'POST', 'PUT', 'DELETE'])
def product_list(request, pk=None):
    # -------------------- GET --------------------
    if request.method == 'GET':
        if pk:  # Get single product
            try:
                product = Product.objects.get(pk=pk)
                serializer = ProductSerializer(product)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Product.DoesNotExist:
                return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
        else:  # Get all products
            products = Product.objects.all()
            serializer = ProductSerializer(products, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

    # -------------------- POST --------------------
    elif request.method == 'POST':
        bank_id = request.data.get("bank")
        product_title = request.data.get("product_title")

        # Check for duplicate product in the same bank
        if Product.objects.filter(bank_id=bank_id, product_title__iexact=product_title).exists():
            return Response(
                {"error": f"A product with title '{product_title}' already exists for bank ID {bank_id}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()  # SalaryCriteria automatically handled by serializer
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # -------------------- PUT --------------------
    elif request.method == 'PUT':
        if not pk:
            return Response({"error": "Product ID required for update"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        bank_id = request.data.get("bank") or product.bank_id
        product_title = request.data.get("product_title") or product.product_title

        # Check for duplicate product_title in the same bank (excluding current product)
        if Product.objects.filter(bank_id=bank_id, product_title__iexact=product_title).exclude(id=product.id).exists():
            return Response(
                {"error": f"A product with title '{product_title}' already exists for bank ID {bank_id}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ProductSerializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()  # SalaryCriteria automatically updated/created
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # -------------------- DELETE --------------------
    elif request.method == 'DELETE':
        if not pk:
            return Response({"error": "Product ID required for delete"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            product = Product.objects.get(pk=pk)
            product.delete()
            return Response({"message": "Product deleted successfully"}, status=status.HTTP_200_OK)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
        
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
        else:
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


@api_view(["GET"])
def get_all_eligibility_checks(request):
    """
    Get all customers who have checked their loan eligibility.
    Includes personal details, salary, company category,
    age, and all eligible banks/products.
    """
    try:
        # ✅ Removed ordering by updated_at
        customers = Customer.objects.all()

        if not customers.exists():
            return Response({
                "status": "success",
                "message": "No customers have checked eligibility yet.",
                "data": []
            }, status=status.HTTP_200_OK)

        response_data = []

        for customer in customers:
            # Calculate age
            age = None
            if customer.dob:
                today = date.today()
                age = today.year - customer.dob.year - (
                    (today.month, today.day) < (customer.dob.month, customer.dob.day)
                )

            # Get company category
            company_category = None
            company_name = getattr(customer, "companyName", "")
            if company_name:
                company_obj = Company.objects.filter(company_name__iexact=company_name).first()
                if company_obj and company_obj.category:
                    company_category = company_obj.category
                else:
                    company_category, _ = CompanyCategory.objects.get_or_create(category_name="UNLISTED")
            else:
                company_category, _ = CompanyCategory.objects.get_or_create(category_name="UNLISTED")

            # Get eligible banks for this customer
            eligible_banks = []
            for bank in Bank.objects.all():
                bank_pins = bank.get_pincode_list()
                if customer.pincode not in bank_pins:
                    continue  # skip if pincode not served

                for product in Product.objects.filter(bank=bank):
                    # Check age range
                    if product.min_age and product.max_age:
                        if not (product.min_age <= age <= product.max_age):
                            continue

                    # Salary check
                    salary_criteria = SalaryCriteria.objects.filter(
                        product=product, category=company_category
                    )

                    if not salary_criteria.exists():
                        continue

                    for criteria in salary_criteria:
                        if float(customer.salary) >= float(criteria.min_salary):
                            eligible_banks.append({
                                "bank_id": bank.id,
                                "bank_name": bank.bank_name,
                                "product_id": product.id,
                                "product_name": product.product_title,
                                "min_salary_required": float(criteria.min_salary),
                                "applicant_salary": float(customer.salary),
                                "roi_range": f"{product.min_roi}%-{product.max_roi}%" if product.min_roi and product.max_roi else "N/A",
                                "tenure_range": f"{product.min_tenure}-{product.max_tenure} months" if product.min_tenure and product.max_tenure else "N/A",
                                "loan_amount_range": {
                                    "min": float(product.min_loan_amount) if product.min_loan_amount else 0,
                                    "max": float(product.max_loan_amount) if product.max_loan_amount else float(customer.salary) * 5
                                }
                            })
                            break  # only need one valid criteria

            # Build customer data
            customer_data = CustomerSerializer(customer).data
            customer_data.update({
                "age": age,
                "company_category": company_category.category_name if company_category else "N/A",
                "eligibility_status": "Eligible" if eligible_banks else "Not Eligible",
                "eligible_banks_count": len(eligible_banks),
                "eligible_banks": eligible_banks,
                "last_eligibility_check": customer.last_eligibility_check  # ✅ added
            })

            response_data.append(customer_data)

        return Response({
            "status": "success",
            "message": "All customers who checked eligibility",
            "count": len(response_data),
            "data": response_data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            "status": "error",
            "message": "Error while fetching eligibility data",
            "error": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
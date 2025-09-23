from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from datetime import date
from .models import Customer, Bank, LoanRule, CustomerInterest
from .serializers import CustomerSerializer, BankSerializer, LoanRuleSerializer, CustomerInterestSerializer

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


@api_view(['GET', 'POST'])
def bank_list(request):
    if request.method == 'GET':
        banks = Bank.objects.all()
        serializer = BankSerializer(banks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = BankSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
# get bank details by pincode
@api_view(['GET'])
def banks_by_pincode(request,pincode):
    banks = Bank.objects.filter(pincode=pincode)
    serializer = BankSerializer(banks, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

# Get all loan rules OR create a new one
@api_view(['GET','POST'])
def loanrule_list(request):
    if request.method == 'GET':
        loanrules = LoanRule.objects.all()
        serializer = LoanRuleSerializer(loanrules, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = LoanRuleSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

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
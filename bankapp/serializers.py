from rest_framework import serializers
from .models import Customer, Bank , LoanRule, CustomerInterest

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'
        extra_kwargs = {
            "email": {"validators": []},   # disable default unique validation
            "phone": {"validators": []},
            "pan": {"validators": []},
        }
        
    def create(self, validated_data):
        email = validated_data.get("email")
        phone = validated_data.get("phone")
        pan = validated_data.get("pan")

        # Check if customer exists by email OR phone OR pan
        customer = Customer.objects.filter(email=email).first() \
                   or Customer.objects.filter(phone=phone).first() \
                   or Customer.objects.filter(pan=pan).first()

        if customer:
            # Update existing record
            for attr, value in validated_data.items():
                setattr(customer, attr, value)
            customer.save()
            self.instance = customer
            return customer
        else:
            # Create new record
            return Customer.objects.create(**validated_data)
        
class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bank
        fields = '__all__'

class LoanRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanRule
        fields = '__all__'        

class CustomerInterestSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    bank_name = serializers.CharField(source="bank.bank_name", read_only=True)

    class Meta:
        model = CustomerInterest
        fields = ["id", "customer", "customer_name", "bank", "bank_name"]        
        
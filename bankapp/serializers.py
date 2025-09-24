from rest_framework import serializers
from .models import Customer, Bank , LoanRule, CustomerInterest


class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    # Hardcoded credentials
    ADMIN_EMAIL = "admin@example.com"
    ADMIN_PASSWORD = "admin123"

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        if email != self.ADMIN_EMAIL or password != self.ADMIN_PASSWORD:
            raise serializers.ValidationError("Invalid admin credentials")

        return attrs



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
    bank_image_url = serializers.SerializerMethodField()
    class Meta:
        model = Bank
        fields = '__all__'
    def get_bank_image_url(self, obj):
        if obj.bank_image:
            return obj.bank_image.url  
        return None

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
        
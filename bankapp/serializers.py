from rest_framework import serializers
from .models import Customer, Bank , LoanRule, CustomerInterest, Product, User


# 🔹 Serializer for login
class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        try:
            user = User.objects.get(email=email, role="admin")
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid admin credentials")

        if not user.check_password(password):
            raise serializers.ValidationError("Invalid admin credentials")

        attrs["user"] = user
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
    pincode_list = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        help_text="Send a list of pincodes, e.g., ['110001','110002']"
    )

    class Meta:
        model = Bank
        fields = ['id', 'bank_name', 'pincode', 'pincode_list', 'bank_image', 'bank_image_url']

    def get_bank_image_url(self, obj):
        if obj.bank_image:
            return obj.bank_image.url  
        return None
    
    # ✅ custom validation for pincode_list
    def validate_pincode_list(self, value):
        for pin in value:
            if not pin.isdigit() or len(pin) != 6:
                raise serializers.ValidationError(f"Invalid pincode: {pin}. Must be exactly 6 digits.")
        return value

    # ✅ custom validation for unique bank name
    def validate_bank_name(self, value):
        qs = Bank.objects.filter(bank_name__iexact=value)
        if self.instance:  # if update, exclude current instance
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Bank with this name already exists.")
        return value

    def create(self, validated_data):
        pincode_list = validated_data.pop('pincode_list', [])
        if pincode_list:
            validated_data['pincode'] = ','.join(pincode_list)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Handle pincode_list if provided
        pincode_list = validated_data.pop('pincode_list', None)
        if pincode_list is not None:
            validated_data['pincode'] = ','.join(pincode_list)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Return pincode as a list instead of a comma string
        data['pincode'] = instance.get_pincode_list()
        return data

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
        
class ProductSerializer(serializers.ModelSerializer):
    # bank_name is read-only, fetched from the related Bank model
    bank_name = serializers.CharField(source="bank.bank_name", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "bank",          # this is bank_id
            "bank_name",     # comes from related bank
            "product_title",
            "min_age",
            "max_age",
            "min_tenure",
            "max_tenure",
            "min_loan_amount",
            "max_loan_amount",
            "min_roi",
            "max_roi",
            "foir_details",
        ]        

# 🔹 Serializer for creating/updating users (admins)
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "password", "role"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

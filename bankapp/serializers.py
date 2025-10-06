from rest_framework import serializers
from .models import Customer, Bank, CustomerInterest, Product, User, ManagedCard, CompanyCategory, Company, SalaryCriteria


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
    
    class Meta:
        model = Bank
        fields = ['id', 'bank_name', 'pincode', 'bank_image', 'bank_image_url']

    def get_bank_image_url(self, obj):
        if obj.bank_image:
            return obj.bank_image.url
        return None

    # ✅ Validate bank name uniqueness
    def validate_bank_name(self, value):
        qs = Bank.objects.filter(bank_name__iexact=value)
        if self.instance:  # Exclude current instance during update
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Bank with this name already exists.")
        return value

    # ✅ Validate pincode field
    def validate_pincode(self, value):
        if not value:
            return value  # allow blank/null if model allows
        pincodes = [p.strip() for p in value.split(',') if p.strip()]
        for pin in pincodes:
            if not pin.isdigit() or len(pin) != 6:
                raise serializers.ValidationError(f"Invalid pincode: {pin}. Must be exactly 6 digits.")
        # Store back as comma-separated string
        return ','.join(pincodes)

    # ✅ Ensure pincodes are returned as a list in response
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.pincode:
            data['pincode'] = [p.strip() for p in instance.pincode.split(',') if p.strip()]
        else:
            data['pincode'] = []
        return data

class CustomerInterestSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    bank_name = serializers.CharField(source="bank.bank_name", read_only=True)
    product_title = serializers.CharField(source="product.product_title", read_only=True)

    class Meta:
        model = CustomerInterest
        fields = ["id", "customer", "customer_name", "bank", "bank_name","product","product_title"]      

class SalaryCriteriaSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.product_title", read_only=True)
    category_name = serializers.CharField(source="category.category_name", read_only=True)

    class Meta:
        model = SalaryCriteria
        fields = ['salary_id', 'product', 'product_name', 'category', 'category_name', 'min_salary']

        
# Product Serializer
from rest_framework import serializers
from .models import Product, SalaryCriteria, CompanyCategory

class SalaryCriteriaSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.category_name", read_only=True)

    class Meta:
        model = SalaryCriteria
        fields = ['salary_id','product', 'category', 'category_name', 'min_salary']

class ProductSerializer(serializers.ModelSerializer):
    salary_criteria = SalaryCriteriaSerializer(many=True, read_only=True)

    # Accept categories from frontend as dict
    categories = serializers.DictField(write_only=True, required=False)

    class Meta:
        model = Product
        fields = [
            "id",
            "bank",
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
            "categories",
            "salary_criteria",
        ]

    def create(self, validated_data):
        categories_input = validated_data.pop("categories", {})

        # Create Product
        product = super().create(validated_data)

        # Create SalaryCriteria entries
        for key, salary in categories_input.items():
            if salary is None:
                continue
            # Replace underscores with spaces to match your CompanyCategory names
            category_name = key.replace("_", " ")
            category, _ = CompanyCategory.objects.get_or_create(category_name=category_name)
            SalaryCriteria.objects.create(
                product=product,
                category=category,
                min_salary=salary
            )

        return product

    def update(self, instance, validated_data):
        categories_input = validated_data.pop("categories", {})

        # Update Product fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update or create SalaryCriteria entries
        for key, salary in categories_input.items():
            if salary is None:
                continue
            category_name = key.replace("_", " ")
            category, _ = CompanyCategory.objects.get_or_create(category_name=category_name)
            SalaryCriteria.objects.update_or_create(
                product=instance,
                category=category,
                defaults={"min_salary": salary}
            )

        return instance
    

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

class ManagedCardSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ManagedCard
        fields = ['id', 'title', 'url', 'image', 'image_url']

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None
    
class CompanyCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyCategory
        fields = "__all__"    

    def validate_category_name(self, value):
        # Case-insensitive uniqueness check
        qs = CompanyCategory.objects.filter(category_name__iexact=value)

        # Exclude current instance in case of update
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError("Category name already exists (case-insensitive).")

        return value

class CompanySerializer(serializers.ModelSerializer):
    category = CompanyCategorySerializer(read_only=True)   # show category details
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=CompanyCategory.objects.all(), write_only=True, source="category"
    )

    class Meta:
        model = Company
        fields = ['company_id', 'company_name', 'category', 'category_id']


        
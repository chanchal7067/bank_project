from django.db import models
from cloudinary.models import CloudinaryField
from django.contrib.auth.hashers import make_password, check_password


class Customer(models.Model):
    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True, max_length=100)
    phone = models.CharField(unique=True, max_length=15)
    dob = models.DateField(null=True, blank=True)
    pan = models.CharField(unique=True, max_length=20)
    employment_type = models.CharField(max_length=50, null=True, blank=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    city = models.CharField(max_length=50, null=True, blank=True)
    pincode = models.CharField(max_length=10, null=True, blank=True)
    existing_loan = models.CharField(max_length=10, null=True, blank=True)
    annualIncome = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    departmentName = models.CharField(max_length=100, null=True, blank=True)
    designationName = models.CharField(max_length=100, null=True, blank=True)
    companyName = models.CharField(max_length=100, null=True, blank=True)
    designation = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.full_name


class Bank(models.Model):
    bank_name = models.CharField(max_length=100)
    pincode = models.CharField(max_length=500, null=True, blank=True,help_text="Enter multiple pincodes separated by commas, e.g., 110001,110002")
    bank_image = CloudinaryField("image", null=True, blank=True)  
    
    def __str__(self):
        return self.bank_name
    
    def get_pincode_list(self):
        if self.pincode:
            return [p.strip() for p in self.pincode.split(",")]
        return []

    
    def has_pincode(self, pincode):
        """Check if the bank serves the given pincode"""
        return pincode in self.get_pincode_list()


class LoanRule(models.Model):
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name="loan_rules")
    min_salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    job_type = models.CharField(max_length=50, null=True, blank=True)
    min_age = models.IntegerField(null=True, blank=True)
    max_age = models.IntegerField(null=True, blank=True)
    
    tenure = models.IntegerField(help_text="Tenure in months or years", null=True, blank=True)
    min_rate = models.FloatField(null=True, blank=True)
    max_rate = models.FloatField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.bank.bank_name} Rule ({self.min_salary}+)"


class CustomerInterest(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="interests")
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name="customer_interests")

    def __str__(self):
        return f"{self.customer.full_name} - {self.bank.bank_name}"

class Product(models.Model):
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name="products")
    product_title = models.CharField(max_length=150)

    # Age range
    min_age = models.IntegerField(null=True, blank=True)
    max_age = models.IntegerField(null=True, blank=True)

    # Tenure range (in months or years as per your use-case)
    min_tenure = models.IntegerField(null=True, blank=True)
    max_tenure = models.IntegerField(null=True, blank=True)

    # Loan amount range
    min_loan_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    max_loan_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    # ROI range
    min_roi = models.FloatField(null=True, blank=True)
    max_roi = models.FloatField(null=True, blank=True)

    salary = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    # FOIR (string so it can store formatted descriptions like "40% of salary")
    foir_details = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.bank.bank_name} - {self.product_title}"

# 🔹 New User/Admin model
class User(models.Model):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("user", "User"),
    )

    email = models.EmailField(unique=True, max_length=100)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="user")

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.email} ({self.role})"
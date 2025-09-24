from django.db import models
from cloudinary.models import CloudinaryField


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
    state = models.CharField(max_length=50, null=True, blank=True)
    pincode = models.CharField(max_length=10, null=True, blank=True)
    bank_image = CloudinaryField("image", null=True, blank=True)  
    
    def __str__(self):
        return self.bank_name


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

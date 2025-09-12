from django.urls import path
from . import views

urlpatterns = [
    path('customers/', views.create_customer, name='create_customer'),

    path("banks/", views.bank_list, name="bank-list"),
    path("banks/pincode/<str:pincode>/", views.banks_by_pincode, name="banks-by-pincode"),

    path("loanrules/", views.loanrule_list, name="loanrule-list"),
    path("loanrules/bank/<int:bank_id>/", views.loanrules_by_bank, name="loanrules-by-bank"),
    
    path("customers/with-eligible-banks/", views.customer_with_eligible_banks, name="customer-with-eligible-banks"),

    path("customer-interests/", views.customer_interest_list_create, name="customer-interest-list-create"),
    path("customer-interests/customer/<int:customer_id>/", views.customer_interests_by_customer, name="customer-interests-by-customer"),

]
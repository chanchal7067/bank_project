from django.urls import path
from . import views

urlpatterns = [
    path("admin/login/", views.admin_login, name="admin_login"),  
    path("admin/create/", views.create_admin, name="create-admin"),
    path("admin/update/<int:pk>/", views.update_admin, name="update-admin"),

    path("customer/create-or-eligible/", views.customer_create_or_eligible_banks, name="customer_create_or_eligible_banks"),

    path("banks/", views.bank_list_create, name="bank_list"),              # GET all, POST
    path("banks/<int:pk>/", views.bank_detail, name="bank_detail"),  # GET one, PUT, DELETE
    path("banks/pincode/<str:pincodes>/", views.banks_by_pincodes, name="banks-by-pincode"),


    path("customer-interests/", views.customer_interest_list_create, name="customer-interest-list-create"),
    path("customer-interests/customer/<int:customer_id>/", views.customer_interests_by_customer, name="customer-interests-by-customer"),

    path("products/", views.product_list, name="product-list-create"),
    path("products/<int:pk>/", views.product_list, name="product-detail"),

    path("products/bank/<int:bank_id>/", views.get_products_by_bank, name="products-by-bank"),

    path('managed-cards/', views.managed_card_list_create, name='managed-card-list-create'),
    path('managed-cards/<int:pk>/', views.managed_card_detail, name='managed-card-detail'),
    
    path('company-categories/', views.company_category_list_create, name='company-category-list'),
    path('company-categories/<int:pk>/', views.company_category_detail, name='company-category-detail'),
    
    path('companies/', views.company_list_create, name="company-list-create"),
    path('companies/<int:pk>/', views.company_detail, name="company-detail"),

    path('salary-criteria/', views.salary_criteria_list_create, name="salary-criteria-list-create"),
    path('salary-criteria/<int:pk>/', views.salary_criteria_detail, name="salary-criteria-detail"),

    path ('get-all-eligiblity-checks/', views.get_all_eligibility_checks, name='get-all-eligiblity-checks'),
]
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('pricing/',  views.pricing_view,  name='pricing'),
    path('checkout/', views.checkout_view, name='checkout'),
]

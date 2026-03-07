import razorpay
from backend.config import Config

client = razorpay.Client(auth=(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET))

def create_razorpay_order(amount, currency='INR', business_account_id=None):
    """
    Creates a Razorpay order using Razorpay Route (Split Payments).
    Automates SaaS revenue by taking a 5% platform fee.
    """
    total_amount_paise = int(amount * 100)
    platform_fee_paise = int(total_amount_paise * 0.05) # 5% SaaS commission
    business_routing_paise = total_amount_paise - platform_fee_paise
    
    data = {
        'amount': total_amount_paise, 
        'currency': currency,
        'payment_capture': 1
    }
    
    # If standard marketplace routing was fully configured with linked accounts
    if business_account_id:
        data['transfers'] = [
            {
                "account": business_account_id,
                "amount": business_routing_paise,
                "currency": currency,
                "notes": {
                    "branch": "Main"
                },
                "linked_account_notes": [
                    "branch"
                ],
                "on_hold": 0
            }
        ]
        
    return client.order.create(data=data)

def verify_payment_signature(payment_id, order_id, signature):
    """Verifies the webhook signature or frontend callback signature."""
    params_dict = {
        'razorpay_payment_id': payment_id,
        'razorpay_order_id': order_id,
        'razorpay_signature': signature
    }
    try:
        client.utility.verify_payment_signature(params_dict)
        return True
    except:
        return False

import os
import json
import tempfile

import requests
import replicate
import stripe
from django.conf import settings
from .models import Product, Profile
from odoo_sync.models import OdooProduct

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache

from groq import Groq, APIConnectionError, RateLimitError, APIStatusError
from dotenv import load_dotenv

from .forms import CustomUserCreationForm, ProductForm
from .models import Product

load_dotenv()

# ── Groq client (singleton) ──────────────────────────────────────────────────

_groq_client = None


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY is not set in your .env file.")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


MODEL         = "llama-3.3-70b-versatile"
MAX_TURNS     = 20
SYSTEM_PROMPT = "You are a helpful, concise, and friendly AI assistant."

# ── Auth views ───────────────────────────────────────────────────────────────

@login_required
def home_view(request):
    products = OdooProduct.objects.filter(sync_status="SYNCED", odoo_active=True)[:12]
    return render(request, "home.html", {"odoo_products": products})


def register_view(request):
    """Handle user registration"""
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful! Please log in.")
            return redirect("login")
    else:
        form = CustomUserCreationForm()
    return render(request, "register.html", {"form": form})


def login_view(request):
    """Handle user login"""
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("home")
    else:
        form = AuthenticationForm()
    return render(request, "login.html", {"form": form})


def logout_view(request):
    """Handle user logout"""
    logout(request)
    return redirect("login")

# ── Product views ─────────────────────────────────────────────────────────────

@login_required
def sell_product_view(request):
    """Handle product listing by sellers"""
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = request.user
            product.is_available = False
            product.is_upcycled = form.cleaned_data['is_upcycled'] == 'True'
            product.save()
            messages.success(request, "Product listed successfully! It will be reviewed and made available soon.")
            form = ProductForm(initial={'is_available': True})
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ProductForm(initial={'is_available': True})
    return render(request, 'sellproduct.html', {'form': form})


def explore_collection_view(request):
    """Display all available products (Internal & Odoo) with search functionality"""
    query = request.GET.get('q')
    
    # Internal Products
    products = Product.objects.filter(is_available=True)
    
    # Odoo Products
    odoo_products = OdooProduct.objects.filter(sync_status="SYNCED", odoo_active=True)

    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )
        odoo_products = odoo_products.filter(
            Q(odoo_name__icontains=query) | Q(odoo_categ_name__icontains=query)
        )

    return render(request, 'explore_collection.html', {
        'products': products,
        'odoo_products': odoo_products
    })


def buy_product_view(request):
    """Display products available for purchase"""
    products = Product.objects.filter(is_available=True)
    return render(request, 'buyproduct.html', {'products': products})


def cart_view(request):
    """Display the user's shopping cart"""
    cart = request.session.get('cart', {})
    cart_items = []
    total = 0

    for item_id, quantity in cart.items():
        if item_id.startswith('odoo_'):
            real_id = item_id.replace('odoo_', '')
            product = get_object_or_404(OdooProduct, id=real_id)
            price = product.odoo_price
            name = product.odoo_name
            desc = product.odoo_categ_name or "Upcycled Product"
            image_url = None 
            is_odoo = True
        else:
            product = get_object_or_404(Product, id=item_id)
            price = product.discounted_price()
            name = product.name
            desc = product.description
            image_url = product.image.url
            is_odoo = False

        item_total = price * quantity
        cart_items.append({
            'product': product, 
            'quantity': quantity, 
            'total': item_total,
            'display_name': name,
            'display_desc': desc,
            'display_price': price,
            'display_image': image_url,
            'is_odoo': is_odoo,
            'item_id': item_id
        })
        total += item_total

    return render(request, 'cart.html', {'cart_items': cart_items, 'total': total})


def add_to_cart(request, product_id):
    """Add a product to the shopping cart"""
    if product_id.startswith('odoo_'):
        real_id = product_id.replace('odoo_', '')
        get_object_or_404(OdooProduct, id=real_id)
    else:
        get_object_or_404(Product, id=product_id)

    cart = request.session.get('cart', {})
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    request.session['cart'] = cart
    messages.success(request, 'Product added to cart!')
    
    next_url = request.POST.get('next')
    if not next_url:
        next_url = request.META.get('HTTP_REFERER', 'explore_collection')
    
    return redirect(next_url)


def remove_from_cart(request, product_id):
    """Decrease quantity of a product in the cart"""
    cart = request.session.get('cart', {})
    if str(product_id) in cart:
        if cart[str(product_id)] > 1:
            cart[str(product_id)] -= 1
        else:
            del cart[str(product_id)]
    request.session['cart'] = cart
    return redirect('cart')


def delete_from_cart(request, product_id):
    """Remove a product completely from the cart"""
    cart = request.session.get('cart', {})
    if str(product_id) in cart:
        del cart[str(product_id)]
    request.session['cart'] = cart
    return redirect('cart')


def hire_designer_view(request):
    """Display the designer hiring page"""
    return render(request, 'hire_designer.html')

# ── AI image generation ───────────────────────────────────────────────────────

@csrf_exempt
def generate_image(request):
    """Handle AI image generation requests"""
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    prompt     = request.POST.get("prompt", "")
    image_file = request.FILES.get("image")

    if not image_file or not prompt:
        return JsonResponse({"error": "Missing image or prompt"}, status=400)

    temp_img_path = os.path.join(tempfile.gettempdir(), image_file.name)
    try:
        with open(temp_img_path, "wb") as f:
            for chunk in image_file.chunks():
                f.write(chunk)

        output = replicate.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input={
                "prompt":   prompt,
                "image":    open(temp_img_path, "rb"),
                "strength": 0.7,
            },
        )
        return JsonResponse({"image_url": output[0]})
    finally:
        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)

# ── Chat views ────────────────────────────────────────────────────────────────

def chat_page(request):
    """Render the chat shell; history lives in the session."""
    request.session.setdefault("chat_history",[])
    return render(request, "chat/chat.html", {
        "chat_history": request.session["chat_history"],
    })


@require_http_methods(["POST"])
def chat_send(request):
    """
    Body   : { "message": "<user text>" }   (JSON)
    Returns: { "reply": "...", "status": "success" }
          or { "error": "...", "code": "..." }
    """
    ip            = request.META.get("REMOTE_ADDR", "unknown")
    key           = f"chat_rate_limit_{ip}"
    request_count = cache.get(key, 0)

    if request_count >= 10:
        return JsonResponse(
            {"error": "Too many requests. Please wait a minute.", "code": "rate_limit"},
            status=429,
        )
    cache.set(key, request_count + 1, 60)

    try:
        body         = json.loads(request.body)
        user_message = body.get("message", "").strip()
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"error": "Invalid request format.", "code": "bad_request"},
            status=400,
        )

    if not user_message:
        return JsonResponse(
            {"error": "Message cannot be empty.", "code": "bad_request"},
            status=400,
        )

    history: list = request.session.get("chat_history",[])
    history.append({"role": "user", "content": user_message})
    trimmed = history[-(MAX_TURNS * 2):]

    try:
        client     = get_groq_client()
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + trimmed,
            temperature=0.7,
            max_tokens=1024,
        )
        reply = completion.choices[0].message.content.strip()

    except RateLimitError:
        history.pop()
        return JsonResponse(
            {"error": "Groq rate limit reached. Please wait and try again.", "code": "rate_limit"},
            status=429,
        )
    except APIConnectionError:
        history.pop()
        return JsonResponse(
            {"error": "Could not reach the AI service. Check your connection.", "code": "connection_error"},
            status=503,
        )
    except APIStatusError as exc:
        history.pop()
        return JsonResponse(
            {"error": f"API error ({exc.status_code}): {exc.message}", "code": "api_error"},
            status=502,
        )
    except EnvironmentError as exc:
        history.pop()
        return JsonResponse(
            {"error": str(exc), "code": "config_error"},
            status=500,
        )

    history.append({"role": "assistant", "content": reply})
    request.session["chat_history"] = history
    request.session.modified = True

    return JsonResponse({"reply": reply, "status": "success"})


@require_http_methods(["POST"])
def chat_clear(request):
    """Clear chat history from session"""
    request.session["chat_history"] =[]
    request.session.modified = True
    return JsonResponse({"status": "cleared"})


# ── Stripe Payment Views ───────────────────────────────────────────────────────

def checkout_view(request):
    cart = request.session.get('cart', {})
    if not cart:
        messages.warning(request, "Your cart is empty.")
        return redirect('explore_collection')

    # Stripe Secret Key Set করা হলো
    stripe.api_key = settings.STRIPE_SECRET_KEY

    line_items, display_items, total = [], [], 0

    for item_id, quantity in cart.items():
        if item_id.startswith('odoo_'):
            real_id = item_id.replace('odoo_', '')
            product = get_object_or_404(OdooProduct, id=real_id)
            price = product.odoo_price
            name = product.odoo_name
            is_odoo = True
        else:
            product = get_object_or_404(Product, id=item_id)
            price = product.discounted_price()
            name = product.name
            is_odoo = False

        unit_price = int(price * 100) # Stripe cents এ হিসাব করে
        item_total = price * quantity
        total += item_total
        
        display_items.append({
            'product': product, 
            'quantity': quantity, 
            'total': item_total,
            'is_odoo': is_odoo,
            'display_name': name,
            'display_price': price
        })
        
        line_items.append({
            'price_data': {
                'currency': 'usd',
                'unit_amount': unit_price,
                'product_data': {'name': name},
            },
            'quantity': quantity,
        })

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=request.build_absolute_uri('/checkout/success/') + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.build_absolute_uri('/checkout/cancel/'),
        )
    except stripe.error.StripeError as e:
        messages.error(request, f"Payment setup failed: {e.user_message}")
        return redirect('cart')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('cart')

    return render(request, 'checkout.html', {
        'display_items': display_items,
        'total': total,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
        'session_id': session.id,
    })


def payment_success(request):
    session_id = request.GET.get('session_id')
    order_info = None
    
    # Stripe Secret Key Set করা হলো
    stripe.api_key = settings.STRIPE_SECRET_KEY

    if session_id:
        try:
            session    = stripe.checkout.Session.retrieve(session_id)
            order_info = {
                'amount':   session.amount_total / 100,
                'currency': session.currency.upper(),
                'email':    session.customer_details.email if session.customer_details else '',
            }
        except stripe.error.StripeError:
            pass
            
    # কার্ট খালি করে দেওয়া হলো পেমেন্ট সফল হওয়ার পর
    request.session['cart'] = {}
    request.session.modified = True
    return render(request, 'payment_success.html', {'order_info': order_info})


def payment_cancel(request):
    return render(request, 'payment_cancel.html')


import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.mail import send_mail
from django.conf import settings


@require_http_methods(["POST"])
def hire_designer_request(request):
    """
    Receives designer hire request via AJAX, sends a confirmation
    email, and returns a WhatsApp deep-link for the user.
    """
    try:
        body    = json.loads(request.body)
        name    = body.get("name", "").strip()
        charge  = body.get("charge", "0").strip()
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid request."}, status=400)

    if not name:
        return JsonResponse({"error": "Designer name is missing."}, status=400)

    # ── Determine recipient email ────────────────────────────────────────
    user_email = (
        request.user.email
        if request.user.is_authenticated and request.user.email
        else None
    )

    # ── Send confirmation email ──────────────────────────────────────────
    if user_email:
        subject = f"Remake_X — Your Request to Hire {name}"
        message = (
            f"Hello {request.user.get_full_name() or 'there'},\n\n"
            f"We've received your request to hire designer {name}.\n\n"
            f"📋 Invoice Summary\n"
            f"{'─' * 32}\n"
            f"Designer   : {name}\n"
            f"Session Fee: ${charge} USD\n"
            f"Platform   : Remake_X\n"
            f"{'─' * 32}\n\n"
            f"Our team will connect you with {name} within 24 hours.\n\n"
            f"Thank you for choosing sustainable fashion!\n"
            f"— The Remake_X Team"
        )
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user_email],
                fail_silently=True,
            )
        except Exception:
            pass   # Email failure should not block the response

    # ── Build WhatsApp deep-link ─────────────────────────────────────────
    wa_number = getattr(settings, "DESIGNER_WHATSAPP_NUMBER", "8801XXXXXXXXX")
    wa_text   = (
        f"Hi! I'm interested in hiring designer {name} "
        f"(Session charge: ${charge}) via Remake_X."
    )
    from urllib.parse import quote
    whatsapp_url = f"https://wa.me/{wa_number}?text={quote(wa_text)}"

    return JsonResponse({
        "status":       "success",
        "whatsapp_url": whatsapp_url,
    })



@login_required
def profile_view(request):

    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()

      
        if 'profile_pic' in request.FILES:
            profile.image = request.FILES['profile_pic']
            profile.save()

        messages.success(request, "Profile updated successfully!")
        return redirect('profile')

    selling_products = Product.objects.filter(seller=request.user)
   

    return render(request, 'profile.html', {
        'selling_products': selling_products,
        'profile': profile
    })

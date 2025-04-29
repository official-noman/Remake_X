import requests
import os
import tempfile
import replicate
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from .forms import CustomUserCreationForm, ProductForm
from .models import Product

def get_gemma3_response(prompt):
    """Get response from Gemma 3 model"""
    try:
        health_response = requests.get("http://localhost:11434", timeout=5)
        if health_response.status_code != 200:
            return "Ollama server not responding. Please start it with 'ollama serve'"

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "gemma:2b",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "top_p": 0.9, "max_tokens": 150}
            },
            timeout=10
        )

        if response.status_code == 200:
            return response.json().get("response", "No response from model.")
        return f"Error: {response.status_code} - {response.text}"

    except requests.Timeout:
        return "Request timed out. Please try again."
    except Exception as e:
        return f"Unexpected error: {str(e)}"

@login_required
def home_view(request):
    """Render the home page for authenticated users"""
    return render(request, "home.html")

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
    """Display all available products with search functionality"""
    query = request.GET.get('q')
    products = Product.objects.filter(is_available=True)

    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    return render(request, 'explore_collection.html', {'products': products})

def buy_product_view(request):
    """Display products available for purchase"""
    products = Product.objects.filter(is_available=True)
    return render(request, 'buyproduct.html', {'products': products})

def cart_view(request):
    """Display the user's shopping cart"""
    cart = request.session.get('cart', {})
    cart_items = []
    total = 0

    for product_id, quantity in cart.items():
        product = get_object_or_404(Product, id=product_id)
        item_total = product.discounted_price() * quantity
        cart_items.append({
            'product': product,
            'quantity': quantity,
            'total': item_total
        })
        total += item_total

    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'total': total
    })

def add_to_cart(request, product_id):
    """Add a product to the shopping cart"""
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    request.session['cart'] = cart
    messages.success(request, 'Product added to cart!')
    return redirect(request.META.get('HTTP_REFERER', 'explore_collection'))

def remove_from_cart(request, product_id):
    """Decrease quantity of a product in the cart"""
    product = get_object_or_404(Product, id=product_id)
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

def checkout_view(request):
    """Display the checkout page"""
    return render(request, 'checkout.html')

def hire_designer_view(request):
    """Display the designer hiring page"""
    return render(request, 'hire_designer.html')

@csrf_exempt
def generate_image(request):
    """Handle AI image generation requests"""
    if request.method == "POST":
        prompt = request.POST.get("prompt", "")
        image_file = request.FILES.get("image")

        if not image_file or not prompt:
            return JsonResponse({"error": "Missing image or prompt"}, status=400)

        temp_img_path = os.path.join(tempfile.gettempdir(), image_file.name)
        with open(temp_img_path, "wb") as f:
            for chunk in image_file.chunks():
                f.write(chunk)

        output = replicate.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input={"prompt": prompt, "image": open(temp_img_path, "rb"), "strength": 0.7}
        )

        os.remove(temp_img_path)
        return JsonResponse({"image_url": output[0]})

    return JsonResponse({"error": "POST method required"}, status=405)

@csrf_exempt
def chat_view(request):
    """Handle chat interactions with Gemma 3"""
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    key = f"chat_rate_limit_{ip}"
    request_count = cache.get(key, 0)

    if request_count > 10:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Too many requests. Please wait a minute.'}, status=429)
        messages.error(request, "Too many requests. Please wait a minute.")
        return render(request, 'chat.html', {'messages': request.session.get('messages', [])})

    cache.set(key, request_count + 1, 60)

    if request.method == 'POST':
        user_message = request.POST.get('message', '')
        reply = get_gemma3_response(user_message)

        # Avoid adding duplicate replies
        if 'messages' not in request.session:
            request.session['messages'] = []

        last_message = request.session['messages'][-1] if request.session['messages'] else None
        if last_message and last_message['role'] == 'bot' and last_message['content'] == reply:
            return JsonResponse({'reply': reply, 'status': 'success'})

        request.session['messages'].extend([
            {'role': 'user', 'content': user_message},
            {'role': 'bot', 'content': reply}
        ])
        request.session.modified = True

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'reply': reply, 'status': 'success'})

        return render(request, 'chat.html', {
            'reply': reply,
            'chat_history': request.session['messages']
        })

    return render(request, 'chat.html', {
        'chat_history': request.session.get('messages', [])
    })

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from .forms import CustomUserCreationForm, ProductForm
from .models import Product
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
import replicate
import tempfile
import asyncio
from concurrent.futures import ThreadPoolExecutor
import httpx
import os
import sys

# Windows-specific asyncio setup
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Initialize thread pool executor for async operations
executor = ThreadPoolExecutor(max_workers=4)

async def get_gemma3_response_async(prompt):
    """
    Get response from Gemma 3 model using Ollama API
    Args:
        prompt (str): The input prompt for the model
    Returns:
        str: The model's response or error message
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # First verify Ollama is running
            try:
                health = await client.get("http://localhost:11434")
                if health.status_code != 200:
                    return "Ollama server not responding. Please start it with 'ollama serve'"
            except httpx.ConnectError:
                return "Could not connect to Ollama. Make sure it's running."

            # Make the API request to Gemma 3
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "gemma3",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "max_tokens": 150
                    }
                }
            )

            if response.status_code == 200:
                return response.json().get("response", "No response from model.")
            elif response.status_code == 404:
                return "Gemma 3 model not found. Try running: 'ollama pull gemma:3b'"
            else:
                return f"API Error (Status {response.status_code}): {response.text}"

    except httpx.TimeoutException:
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
            input={
                "prompt": prompt,
                "image": open(temp_img_path, "rb"),
                "strength": 0.7,
            }
        )

        os.remove(temp_img_path)
        return JsonResponse({"image_url": output[0]})

    return JsonResponse({"error": "POST method required"}, status=405)

@csrf_exempt
def chat_view(request):
    """Handle chat interactions with Gemma 3"""
    # Rate limiting (10 requests per minute)
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
        
        # Create new event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Get response from Gemma 3
            reply = loop.run_until_complete(get_gemma3_response_async(user_message))
            
            # Update session with conversation history
            if 'messages' not in request.session:
                request.session['messages'] = []
            
            request.session['messages'].append({'sender': 'user', 'text': user_message})
            request.session['messages'].append({'sender': 'bot', 'text': reply})
            request.session.modified = True
            
            # Handle AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'reply': reply,
                    'status': 'success'
                })
            
            # Handle regular form submissions
            return render(request, 'chat.html', {
                'user_message': user_message,
                'reply': reply,
                'messages': request.session['messages']
            })
            
        except Exception as e:
            error_msg = f"Error processing your request: {str(e)}"
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': error_msg,
                    'status': 'error'
                }, status=500)
            
            messages.error(request, error_msg)
            return render(request, 'chat.html', {
                'messages': request.session.get('messages', [])
            })
            
        finally:
            loop.close()
    
    # GET request - display chat history
    return render(request, 'chat.html', {
        'messages': request.session.get('messages', [])
    })
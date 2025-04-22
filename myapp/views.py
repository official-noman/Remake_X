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
import replicate
import tempfile
import os


# Home View
@login_required
def home_view(request):
    return render(request, "home.html")

# Register View
def register_view(request):
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

# Login View
def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("home")
    else:
        form = AuthenticationForm()
    return render(request, "login.html", {"form": form})

# Logout View
def logout_view(request):
    logout(request)
    return redirect("login")

# Sell Product View
@login_required
def sell_product_view(request):
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

# Explore Collection View
def explore_collection_view(request):
    query = request.GET.get('q')
    products = Product.objects.filter(is_available=True)
    
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )  # Fixed the missing parenthesis here
    
    return render(request, 'explore_collection.html', {'products': products})

# Buy Product View
def buy_product_view(request):
    products = Product.objects.filter(is_available=True)
    return render(request, 'buyproduct.html', {'products': products})

# Cart View
def cart_view(request):
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

# Add to Cart View
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})

    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    request.session['cart'] = cart

    messages.success(request, 'Product added to cart!')
    return redirect(request.META.get('HTTP_REFERER', 'explore_collection'))

# Remove from Cart View
def remove_from_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})

    if str(product_id) in cart:
        if cart[str(product_id)] > 1:
            cart[str(product_id)] -= 1
        else:
            del cart[str(product_id)]

    request.session['cart'] = cart
    return redirect('cart')

# Delete from Cart View
def delete_from_cart(request, product_id):
    cart = request.session.get('cart', {})

    if str(product_id) in cart:
        del cart[str(product_id)]

    request.session['cart'] = cart
    return redirect('cart')

# Checkout View
def checkout_view(request):
    return render(request, 'checkout.html')

# Hire Designer View
def hire_designer_view(request):
    return render(request, 'hire_designer.html')

# AI Image Generation View
@csrf_exempt
def generate_image(request):
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
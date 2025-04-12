from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from .forms import CustomUserCreationForm, ProductForm
from .models import Product
from django.contrib import messages

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
            product.save()
            return redirect('explore_collection')
    else:
        form = ProductForm()
    return render(request, 'sellproduct.html', {'form': form})

# Explore Collection View
from django.shortcuts import render
from django.db.models import Q
from .models import Product

def explore_collection_view(request):

    query = request.GET.get('q')
    
    products = Product.objects.filter(is_available=True)
    
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )
    
    # Pass the filtered products to the template
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

    messages.success(request, 'Product added to cart!')  # Add success message
    return redirect(request.META.get('HTTP_REFERER', 'explore_collection')) 

    # return redirect(request.META.get('HTTP_REFERER', 'explore_collection'))

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

@login_required
def sell_product_view(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = request.user
            product.is_available = False  # Ensure availability
            # is_upcycled_value = request.POST.get("is_upcycled")
            # product.is_upcycled = is_upcycled_value == "Yes"

            product.is_upcycled = form.cleaned_data['is_upcycled'] == 'True' 

            product.save()
            messages.success(request, "Product listed successfully! It will be reviewed and made available soon.")
            form = ProductForm(initial={'is_available': True})
            # return redirect('sellproduct')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ProductForm(initial={'is_available': True})
    
    return render(request, 'sellproduct.html', {'form': form})

# hire designer view
def hire_designer_view(request):
    return render(request, 'hire_designer.html')


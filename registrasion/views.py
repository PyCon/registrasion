import datetime
import zipfile

from . import forms
from . import util
from .models import commerce
from .models import inventory
from .models import people
from .models import conditions
from .controllers.batch import BatchController
from .controllers.cart import CartController
from .controllers.category import CategoryController
from .controllers.credit_note import CreditNoteController
from .controllers.discount import DiscountController
from .controllers.invoice import InvoiceController
from .controllers.item import ItemController
from .controllers.product import ProductController
from .exceptions import CartValidationError

from collections import namedtuple, defaultdict

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms as django_forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError
from django.core.mail import send_mass_mail
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.template import Context, Template, loader
from django.views.decorators.clickjacking import xframe_options_sameorigin

from waffle.decorators import waffle_flag

User = get_user_model()


_GuidedRegistrationSection = namedtuple(
    "GuidedRegistrationSection",
    (
        "title",
        "discounts",
        "description",
        "form",
    )
)


@util.all_arguments_optional
class GuidedRegistrationSection(_GuidedRegistrationSection):
    ''' Represents a section of a guided registration page.

    Attributes:
       title (str): The title of the section.

       discounts ([registrasion.contollers.discount.DiscountAndQuantity, ...]):
            A list of discount objects that are available in the section. You
            can display ``.clause`` to show what the discount applies to, and
            ``.quantity`` to display the number of times that discount can be
            applied.

       description (str): A description of the section.

       form (forms.Form): A form to display.
    '''
    pass


@login_required
@waffle_flag('registration_open')
def guided_registration(request, page_number=None):
    ''' Goes through the registration process in order, making sure user sees
    all valid categories.

    The user must be logged in to see this view.

    Parameter:
        page_number:
            1) Profile form (and e-mail address?)
            2) Ticket type
            3) Remaining products
            4) Mark registration as complete

    Returns:
        render: Renders ``registrasion/guided_registration.html``,
            with the following data::

                {
                    "current_step": int(),  # The current step in the
                                            # registration
                    "sections": sections,   # A list of
                                            # GuidedRegistrationSections
                    "title": str(),         # The title of the page
                    "total_steps": int(),   # The total number of steps
                }

    '''

    PAGE_PROFILE = 1
    PAGE_TICKET = 2
    PAGE_PRODUCTS = 3
    PAGE_TUTORIALS = 4
    PAGE_WORKSHOPS = 5
    PAGE_PRODUCTS_MAX = 6
    TOTAL_PAGES = 6

    ticket_category = inventory.Category.objects.get(
        id=settings.TICKET_PRODUCT_CATEGORY
    )
    tutorials_category = inventory.Category.objects.get(
        id=settings.TUTORIAL_PRODUCT_CATEGORY
    )
    workshops_category = inventory.Category.objects.get(
        id=settings.WORKSHOP_PRODUCT_CATEGORY
    )
    cart = CartController.for_user(request.user)

    attendee = people.Attendee.get_instance(request.user)

    # This guided registration process is only for people who have
    # not completed registration (and has confusing behaviour if you go
    # back to it.)
    if attendee.completed_registration:
        return redirect(review)

    # Calculate the current maximum page number for this user.
    has_profile = hasattr(attendee, "attendeeprofilebase")
    if not has_profile:
        # If there's no profile, they have to go to the profile page.
        max_page = PAGE_PROFILE
        redirect_page = PAGE_PROFILE
    else:
        # We have a profile.
        # Do they have a ticket?
        products = inventory.Product.objects.filter(
            productitem__cart=cart.cart
        )
        products = products.filter(category=ticket_category)

        if products.count() == 0:
            # If no ticket, they can only see the profile or ticket page.
            max_page = PAGE_TICKET
            redirect_page = PAGE_TICKET
        else:
            # If there's a ticket, they should *see* the general products page#
            # but be able to go to the overflow page if needs be.
            max_page = PAGE_PRODUCTS_MAX
            redirect_page = PAGE_PRODUCTS

    if page_number is None or int(page_number) > max_page:
        return redirect("guided_registration", redirect_page)

    page_number = int(page_number)

    next_step = redirect("guided_registration", page_number + 1)

    with BatchController.batch(request.user):

        # This view doesn't work if the conference has sold out.
        available = ProductController.available_products(
            request.user, category=ticket_category
        )
        if not available:
            messages.error(request, "There are no more tickets available.")
            return redirect("dashboard")

        sections = []

        # Build up the list of sections
        if page_number == PAGE_PROFILE:
            # Profile bit
            title = "Attendee information"
            sections = _guided_registration_profile_and_voucher(request)
        elif page_number == PAGE_TICKET:
            # Select ticket
            title = "Select ticket type"
            sections = _guided_registration_products(
                request, GUIDED_MODE_TICKETS_ONLY
            )
        elif page_number == PAGE_PRODUCTS:
            # Select additional items
            title = "Additional items"
            sections = _guided_registration_products(
                request, GUIDED_MODE_ALL_ADDITIONAL
            )
        elif page_number == PAGE_TUTORIALS:
            title = "Tutorials"
            sections = _guided_registration_products(
                request, GUIDED_MODE_TUTORIALS
            )
        elif page_number == PAGE_WORKSHOPS:
            title = "Sponsor Workshops"
            sections = _guided_registration_products(
                request, GUIDED_MODE_WORKSHOPS
            )
        elif page_number == PAGE_PRODUCTS_MAX:
            # Items enabled by things on page 3 -- only shows things
            # that have not been marked as complete.
            title = "More additional items"
            sections = []  # Force termination of flow due to tutorials/workshops as separate pages
            #sections = _guided_registration_products(
            #    request, GUIDED_MODE_EXCLUDE_COMPLETE
            #)

        if not sections:
            # We've filled in every category
            attendee.completed_registration = True
            attendee.save()
            return redirect("review")

        section_errors = []
        if sections and request.method == "POST":
            for section in sections:
                if section.form.contains_errors:
                    section_errors.append(section.title)
            if len(section_errors) == 0:
                # We've successfully processed everything
                return next_step

    data = {
        "current_step": page_number,
        "sections": sections,
        "title": title,
        "total_steps": TOTAL_PAGES,
        "section_errors": section_errors,
    }
    return render(request, "registrasion/guided_registration.html", data)


GUIDED_MODE_TICKETS_ONLY = 2
GUIDED_MODE_ALL_ADDITIONAL = 3
GUIDED_MODE_TUTORIALS = 4
GUIDED_MODE_WORKSHOPS = 5
GUIDED_MODE_EXCLUDE_COMPLETE = 6


@login_required
def _guided_registration_products(request, mode):
    sections = []

    SESSION_KEY = "guided_registration"
    MODE_KEY = "mode"
    CATS_KEY = "cats"

    attendee = people.Attendee.get_instance(request.user)

    # Get the next category
    cats = inventory.Category.objects.order_by("order")  # TODO: default order?

    # Fun story: If _any_ of the category forms result in an error, but other
    # new products get enabled with a flag, those new products will appear.
    # We need to make sure that we only display the products that were valid
    # in the first place. So we track them in a session, and refresh only if
    # the page number does not change. Cheap!

    if SESSION_KEY in request.session:
        session_struct = request.session[SESSION_KEY]
        old_mode = session_struct[MODE_KEY]
        old_cats = session_struct[CATS_KEY]
    else:
        old_mode = None
        old_cats = []

    if mode == old_mode:
        cats = cats.filter(id__in=old_cats)
    elif mode == GUIDED_MODE_TICKETS_ONLY:
        cats = cats.filter(id=settings.TICKET_PRODUCT_CATEGORY)
    elif mode == GUIDED_MODE_ALL_ADDITIONAL:
        cats = (
            cats.exclude(id=settings.TICKET_PRODUCT_CATEGORY)
                .exclude(id=settings.TUTORIAL_PRODUCT_CATEGORY)
                .exclude(id=settings.WORKSHOP_PRODUCT_CATEGORY)
        )
    elif mode == GUIDED_MODE_TUTORIALS:
        cats = cats.filter(id=settings.TUTORIAL_PRODUCT_CATEGORY)
    elif mode == GUIDED_MODE_WORKSHOPS:
        cats = cats.filter(id=settings.WORKSHOP_PRODUCT_CATEGORY)
    elif mode == GUIDED_MODE_EXCLUDE_COMPLETE:
        cats = cats.exclude(id=settings.TICKET_PRODUCT_CATEGORY)
        cats = cats.exclude(id__in=old_cats)

    # We update the session key at the end of this method
    # once we've found all the categories that have available products

    all_products = inventory.Product.objects.filter(
        category__in=cats,
    ).select_related("category")

    seen_categories = []

    with BatchController.batch(request.user):
        available_products = set(ProductController.available_products(
            request.user,
            products=all_products,
        ))
        available_categories = set()
        for product in available_products:
            available_categories.add(product.category)

        available_but_sold_out_products = set(p for p in ProductController.sold_out_products(
            request.user,
            products=all_products,
        ) if p.category in available_categories)

        disabled_products = ProductController.disabled_products(
            request.user,
            products=all_products,
        )

        # Check for conditions where we may hide all but one ticket type.
        if mode == GUIDED_MODE_TICKETS_ONLY:
            filtered_products = []
            for product in available_products:
                product_conditions = product.flagbase_set.select_subclasses(conditions.VoucherFlag)
                for condition in product_conditions:
                    if isinstance(condition, conditions.VoucherFlag):
                        filtered_products.append(product)
                        break
            if len(filtered_products) == 1:
                available_products = filtered_products

        if len(available_products) == 0:
            return []

        has_errors = False

        for category in cats:
            products = [
                i for i in available_products
                if i.category == category
            ]
            sold_out_products = [
                i for i in available_but_sold_out_products
                if i.category == category
            ]
            disabled_products['purchased'] = [
                i for i in disabled_products['purchased']
                if i.category == category
            ]
            disabled_products['pending'] = [
                i for i in disabled_products['pending']
                if i.category == category
            ]

            prefix = "category_" + str(category.id)
            p = _handle_products(request, category, products, sold_out_products, disabled_products, prefix)
            products_form, discounts, products_handled = p

            section = GuidedRegistrationSection(
                title=category.name,
                description=category.description,
                discounts=discounts,
                form=products_form,
            )

            if products or sold_out_products:
                # This product category has items to show.
                sections.append(section)
                seen_categories.append(category)

    # Update the cache with the newly calculated values
    cat_ids = [cat.id for cat in seen_categories]
    request.session[SESSION_KEY] = {MODE_KEY: mode, CATS_KEY: cat_ids}

    return sections


@login_required
def _guided_registration_profile_and_voucher(request):
    voucher_form, voucher_handled = _handle_voucher(request, "voucher")
    profile_form, profile_handled = _handle_profile(request, "profile")

    voucher_section = GuidedRegistrationSection(
        title="Voucher Code",
        form=voucher_form,
    )

    profile_section = GuidedRegistrationSection(
        title="Profile and Personal Information",
        form=profile_form,
    )

    return [voucher_section, profile_section]


@login_required
@waffle_flag('registration_open')
def review(request):
    ''' View for the review page. '''

    return render(
        request,
        "registrasion/review.html",
        {},
    )


@login_required
@waffle_flag('registration_open')
def edit_profile(request):
    ''' View for editing an attendee's profile

    The user must be logged in to edit their profile.

    Returns:
        redirect or render:
            In the case of a ``POST`` request, it'll redirect to ``dashboard``,
            or otherwise, it will render ``registrasion/profile_form.html``
            with data::

                {
                    "form": form,  # Instance of ATTENDEE_PROFILE_FORM.
                }

    '''

    form, handled = _handle_profile(request, "profile")

    if handled and not form.errors:
        messages.success(
            request,
            "Your attendee profile was updated.",
        )
        return redirect("dashboard")

    data = {
        "form": form,
    }
    return render(request, "registrasion/profile_form.html", data)


# Define the attendee profile form, or get a default.
try:
    ProfileForm = util.get_object_from_name(settings.ATTENDEE_PROFILE_FORM)
except:
    class ProfileForm(django_forms.ModelForm):
        class Meta:
            model = util.get_object_from_name(settings.ATTENDEE_PROFILE_MODEL)
            exclude = ["attendee"]


def _handle_profile(request, prefix):
    ''' Returns a profile form instance, and a boolean which is true if the
    form was handled. '''
    attendee = people.Attendee.get_instance(request.user)

    try:
        profile = attendee.attendeeprofilebase
        profile = people.AttendeeProfileBase.objects.get_subclass(
            pk=profile.id,
        )
    except ObjectDoesNotExist:
        profile = None

    name_field = ProfileForm.Meta.model.name_field()
    initial = {}
    if name_field is not None:
        initial[name_field] = request.user.name

    form = ProfileForm(
        request.POST or None,
        initial=initial,
        instance=profile,
        prefix=prefix
    )

    handled = True if request.POST else False

    if request.POST and form.is_valid():
        form.instance.attendee = attendee
        form.save()

    return form, handled


@login_required
@waffle_flag('registration_open')
def product_category(request, category_id):
    ''' Form for selecting products from an individual product category.

    Arguments:
        category_id (castable to int): The id of the category to display.

    Returns:
        redirect or render:
            If the form has been sucessfully submitted, redirect to
            ``dashboard``. Otherwise, render
            ``registrasion/product_category.html`` with data::

                {
                    "category": category,         # An inventory.Category for
                                                  # category_id
                    "discounts": discounts,       # A list of
                                                  # DiscountAndQuantity
                    "form": products_form,        # A form for selecting
                                                  # products
                    "voucher_form": voucher_form, # A form for entering a
                                                  # voucher code
                }

    '''

    PRODUCTS_FORM_PREFIX = "products"
    VOUCHERS_FORM_PREFIX = "vouchers"

    # Handle the voucher form *before* listing products.
    # Products can change as vouchers are entered.
    v = _handle_voucher(request, VOUCHERS_FORM_PREFIX)
    voucher_form, voucher_handled = v

    category_id = int(category_id)  # Routing is [0-9]+
    category = inventory.Category.objects.get(pk=category_id)

    with BatchController.batch(request.user):
        products = ProductController.available_products(
            request.user,
            category=category,
        )

        sold_out_products = ProductController.sold_out_products(
            request.user,
            category=category,
        )

        disabled_products = ProductController.disabled_products(
            request.user,
            category=category,
        )

        if category_id == settings.TICKET_PRODUCT_CATEGORY:
            filtered_products = []
            for product in products:
                product_conditions = product.flagbase_set.select_subclasses(conditions.VoucherFlag)
                for condition in product_conditions:
                    if isinstance(condition, conditions.VoucherFlag):
                        filtered_products.append(product)
                        break
            if len(filtered_products) == 1:
                products = filtered_products

        if not products and not sold_out_products:
            messages.warning(
                request,
                (
                    "There are no products available from category: " +
                    category.name
                ),
            )
            return redirect("dashboard")

        p = _handle_products(request, category, products, sold_out_products, disabled_products, PRODUCTS_FORM_PREFIX)
        products_form, discounts, products_handled = p

    if request.POST and not voucher_handled and not products_form.contains_errors:
        # Only return to the dashboard if we didn't add a voucher code
        # and if there's no errors in the products form
        if products_form.has_changed():
            messages.success(
                request,
                "Your reservations have been updated.",
            )
        return redirect(review)

    data = {
        "category": category,
        "discounts": discounts,
        "form": products_form,
        "voucher_form": voucher_form,
    }

    return render(request, "registrasion/product_category.html", data)


@waffle_flag('registration_open')
@login_required
def voucher_code(request):
    ''' A view *just* for entering a voucher form. '''

    VOUCHERS_FORM_PREFIX = "vouchers"

    # Handle the voucher form *before* listing products.
    # Products can change as vouchers are entered.
    v = _handle_voucher(request, VOUCHERS_FORM_PREFIX)
    voucher_form, voucher_handled = v

    if voucher_handled:
        messages.success(request, "Your voucher code was accepted.")
        return redirect("dashboard")

    data = {
        "voucher_form": voucher_form,
    }

    return render(request, "registrasion/voucher_code.html", data)



def _handle_products(request, category, products, sold_out_products, disabled_products, prefix):
    ''' Handles a products list form in the given request. Returns the
    form instance, the discounts applicable to this form, and whether the
    contents were handled. '''

    current_cart = CartController.for_user(request.user)

    ProductsForm = forms.ProductsForm(category, products, sold_out_products, disabled_products)

    # Create initial data for each of products in category
    items = commerce.ProductItem.objects.filter(
        product__category=category,
        cart=current_cart.cart,
    ).select_related("product")
    quantities = []
    seen = set()

    for item in items:
        if item.product in products:
            quantities.append((item.product, item.quantity, item.price_override, item.additional_data))
            seen.add(item.product)
        else:
            item.delete()

    zeros = set(products) - seen
    for product in zeros:
        quantities.append((product, 0, None, None))

    products_form = ProductsForm(
        request.POST or None,
        product_quantities=quantities,
        prefix=prefix,
    )

    if request.method == "POST" and products_form.is_valid():
        if products_form.has_changed():
            _set_quantities_from_products_form(products_form, current_cart)

        # If category is required, the user must have at least one
        # in an active+valid cart
        if category.required:
            carts = commerce.Cart.objects.filter(user=request.user)
            items = commerce.ProductItem.objects.filter(
                product__category=category,
                cart__in=carts,
            )
            if len(items) == 0:
                products_form.add_error(
                    None,
                    "You must have at least one item from this category",
                )
    handled = False if products_form.contains_errors else True

    # Making this a function to lazily evaluate when it's displayed
    # in templates.

    discounts = util.lazy(
        DiscountController.available_discounts,
        request.user,
        [],
        products,
    )

    return products_form, discounts, handled


def _set_quantities_from_products_form(products_form, current_cart):

    # Makes id_to_quantity, a dictionary from product ID to its quantity
    quantities = [
        (product_id, quantity)
        for product_id, quantity, _, _
        in products_form.product_quantities()
    ]
    id_to_quantity = dict(quantities)

    price_overrides = [
        (product_id, price_override)
        for product_id, _, price_override, _
        in products_form.product_quantities()
    ]
    id_to_price_override = dict(price_overrides)

    selections_with_additional_data = defaultdict(list)
    for product_id, quantity, price_override, additional_data in products_form.product_quantities():
        if additional_data is not None:
            selections_with_additional_data[product_id] += [(quantity, price_override, additional_data)]

    # Get the actual product objects
    pks = [i[0] for i in quantities]
    products = inventory.Product.objects.filter(
        id__in=pks, additional_data__isnull=True,
    ).select_related("category").order_by("id")

    products_with_additional_data = inventory.Product.objects.filter(
        id__in=pks, additional_data__isnull=False,
    ).select_related("category").order_by("id")

    quantities.sort(key=lambda i: i[0])

    # Match the product objects to their quantities
    product_quantities = [
        (product, id_to_quantity[product.id], id_to_price_override[product.id], None)
        for product in products
    ]

    for product in products_with_additional_data:
        for quantity, price_override, additional_data in selections_with_additional_data[product.id]:
            product_quantities.append((product, quantity, price_override, additional_data))

    try:
        current_cart.set_quantities(product_quantities)
    except CartValidationError as ve:
        for ve_field in ve.error_list:
            product, message = ve_field.message
            products_form.add_product_error(product, message)


def _handle_voucher(request, prefix):
    ''' Handles a voucher form in the given request. Returns the voucher
    form instance, and whether the voucher code was handled. '''

    voucher_form = forms.VoucherForm(request.POST or None, prefix=prefix)
    current_cart = CartController.for_user(request.user)

    if (voucher_form.is_valid() and
            voucher_form.cleaned_data["voucher"].strip()):

        voucher = voucher_form.cleaned_data["voucher"]
        voucher = inventory.Voucher.normalise_code(voucher)

        if len(current_cart.cart.vouchers.filter(code=voucher)) > 0:
            # This voucher has already been applied to this cart.
            # Do not apply code
            handled = False
        else:
            try:
                current_cart.apply_voucher(voucher)
            except Exception as e:
                voucher_form.add_error("voucher", e)
            handled = True
    else:
        handled = False

    return (voucher_form, handled)


@login_required
@waffle_flag('registration_open')
def checkout(request, user_id=None):
    ''' Runs the checkout process for the current cart.

    If the query string contains ``fix_errors=true``, Registrasion will attempt
    to fix errors preventing the system from checking out, including by
    cancelling expired discounts and vouchers, and removing any unavailable
    products.

    Arguments:
        user_id (castable to int):
            If the requesting user is staff, then the user ID can be used to
            run checkout for another user.
    Returns:
        render or redirect:
            If the invoice is generated successfully, or there's already a
            valid invoice for the current cart, redirect to ``invoice``.
            If there are errors when generating the invoice, render
            ``registrasion/checkout_errors.html`` with the following data::

                {
                    "error_list", [str, ...]  # The errors to display.
                }

    '''

    if user_id is not None:
        if request.user.has_perm('registrasion.registrasion_admin'):
            user = User.objects.get(id=int(user_id))
        else:
            raise Http404()
    else:
        user = request.user

    current_cart = CartController.for_user(user)

    if "fix_errors" in request.GET and request.GET["fix_errors"] == "true":
        current_cart.fix_simple_errors()
        return redirect("review")

    try:
        current_invoice = InvoiceController.for_cart(current_cart.cart)
    except ValidationError as ve:
        return _checkout_errors(request, ve)

    return redirect("invoice", current_invoice.invoice.id)


def _checkout_errors(request, errors):

    error_list = []
    for error in errors.error_list:
        if isinstance(error, tuple):
            error = error[1]
        error_list.append(error)

    data = {
        "error_list": error_list,
    }

    return render(request, "registrasion/checkout_errors.html", data)


@waffle_flag('registration_open')
def invoice_access(request, access_code):
    ''' Redirects to an invoice for the attendee that matches the given access
    code, if any.

    If the attendee has multiple invoices, we use the following tie-break:

    - If there's an unpaid invoice, show that, otherwise
    - If there's a paid invoice, show the most recent one, otherwise
    - Show the most recent invoid of all

    Arguments:

        access_code (castable to int): The access code for the user whose
            invoice you want to see.

    Returns:
        redirect:
            Redirect to the selected invoice for that user.

    Raises:
        Http404: If the user has no invoices.
    '''

    invoices = commerce.Invoice.objects.filter(
        user__attendee__access_code=access_code,
    ).order_by("-issue_time")

    if not invoices:
        raise Http404()

    unpaid = invoices.filter(status=commerce.Invoice.STATUS_UNPAID)
    paid = invoices.filter(status=commerce.Invoice.STATUS_PAID)

    if unpaid:
        invoice = unpaid[0]  # (should only be 1 unpaid invoice?)
    elif paid:
        invoice = paid[0]  # Most recent paid invoice
    else:
        invoice = invoices[0]  # Most recent of any invoices

    return redirect("invoice", invoice.id, access_code)


@waffle_flag('registration_open')
def invoice(request, invoice_id, access_code=None):
    ''' Displays an invoice.

    This view is not authenticated, but it will only allow access to either:
    the user the invoice belongs to; staff; or a request made with the correct
    access code.

    Arguments:

        invoice_id (castable to int): The invoice_id for the invoice you want
            to view.

        access_code (Optional[str]): The access code for the user who owns
            this invoice.

    Returns:
        render:
            Renders ``registrasion/invoice.html``, with the following
            data::

                {
                    "invoice": models.commerce.Invoice(),
                }

    Raises:
        Http404: if the current user cannot view this invoice and the correct
            access_code is not provided.

    '''

    current_invoice = InvoiceController.for_id_or_404(invoice_id)

    if not current_invoice.can_view(
            user=request.user,
            access_code=access_code,
            ):
        raise Http404()

    data = {
        "invoice": current_invoice.invoice,
    }

    return render(request, "registrasion/invoice.html", data)


@waffle_flag('registration_open')
@xframe_options_sameorigin
def invoice_plain(request, invoice_id, access_code=None):
    ''' Displays an invoice.

    This view is not authenticated, but it will only allow access to either:
    the user the invoice belongs to; staff; or a request made with the correct
    access code.

    Arguments:

        invoice_id (castable to int): The invoice_id for the invoice you want
            to view.

        access_code (Optional[str]): The access code for the user who owns
            this invoice.

    Returns:
        render:
            Renders ``registrasion/invoice.html``, with the following
            data::

                {
                    "invoice": models.commerce.Invoice(),
                }

    Raises:
        Http404: if the current user cannot view this invoice and the correct
            access_code is not provided.

    '''

    current_invoice = InvoiceController.for_id_or_404(invoice_id)

    if not current_invoice.can_view(
            user=request.user,
            access_code=access_code,
            ):
        raise Http404()

    data = {
        "invoice": current_invoice.invoice,
    }

    return render(request, "registrasion/invoice_plain.html", data)


def _staff_only(user):
    ''' Returns true if the user is staff. '''
    return user.has_perm('registrasion.registrasion_admin')


@user_passes_test(_staff_only)
def manual_payment(request, invoice_id):
    ''' Allows staff to make manual payments or refunds on an invoice.

    This form requires a login, and the logged in user needs to be staff.

    Arguments:
        invoice_id (castable to int): The invoice ID to be paid

    Returns:
        render:
            Renders ``registrasion/manual_payment.html`` with the following
            data::

                {
                    "invoice": models.commerce.Invoice(),
                    "form": form,   # A form that saves a ``ManualPayment``
                                    # object.
                }

    '''

    FORM_PREFIX = "manual_payment"

    current_invoice = InvoiceController.for_id_or_404(invoice_id)

    form = forms.ManualPaymentForm(
        request.POST or None,
        prefix=FORM_PREFIX,
    )

    if request.POST and form.is_valid():
        form.instance.invoice = current_invoice.invoice
        form.instance.entered_by = request.user
        form.save()
        current_invoice.update_status()
        form = forms.ManualPaymentForm(prefix=FORM_PREFIX)

    data = {
        "invoice": current_invoice.invoice,
        "form": form,
    }

    return render(request, "registrasion/manual_payment.html", data)


@user_passes_test(_staff_only)
def refund(request, invoice_id):
    ''' Marks an invoice as refunded and requests a credit note for the
    full amount paid against the invoice.

    This view requires a login, and the logged in user must be staff.

    Arguments:
        invoice_id (castable to int): The ID of the invoice to refund.

    Returns:
        redirect:
            Redirects to ``invoice``.

    '''

    current_invoice = InvoiceController.for_id_or_404(invoice_id)

    try:
        current_invoice.refund()
        messages.success(request, "This invoice has been refunded.")
    except ValidationError as ve:
        messages.error(request, ve)

    return redirect("invoice", invoice_id)


@user_passes_test(_staff_only)
def credit_note(request, note_id, access_code=None):
    ''' Displays a credit note.

    If ``request`` is a ``POST`` request, forms for applying or refunding
    a credit note will be processed.

    This view requires a login, and the logged in user must be staff.

    Arguments:
        note_id (castable to int): The ID of the credit note to view.

    Returns:
        render or redirect:
            If the "apply to invoice" form is correctly processed, redirect to
            that invoice, otherwise, render ``registration/credit_note.html``
            with the following data::

                {
                    "credit_note": models.commerce.CreditNote(),
                    "apply_form": form,  # A form for applying credit note
                                         # to an invoice.
                    "refund_form": form, # A form for applying a *manual*
                                         # refund of the credit note.
                    "cancellation_fee_form" : form, # A form for generating an
                                                    # invoice with a
                                                    # cancellation fee
                }

    '''

    note_id = int(note_id)
    current_note = CreditNoteController.for_id_or_404(note_id)

    apply_form = forms.ApplyCreditNoteForm(
        current_note.credit_note.invoice.user,
        request.POST or None,
        prefix="apply_note"
    )

    refund_form = forms.ManualCreditNoteRefundForm(
        request.POST or None,
        prefix="refund_note"
    )

    cancellation_fee_form = forms.CancellationFeeForm(
        request.POST or None,
        prefix="cancellation_fee"
    )

    if request.POST and apply_form.is_valid():
        inv_id = apply_form.cleaned_data["invoice"]
        invoice = commerce.Invoice.objects.get(pk=inv_id)
        current_note.apply_to_invoice(invoice)
        messages.success(
            request,
            "Applied credit note %d to invoice." % note_id,
        )
        return redirect("invoice", invoice.id)

    elif request.POST and refund_form.is_valid():
        refund_form.instance.entered_by = request.user
        refund_form.instance.parent = current_note.credit_note
        refund_form.save()
        messages.success(
            request,
            "Applied manual refund to credit note."
        )
        refund_form = forms.ManualCreditNoteRefundForm(
            prefix="refund_note",
        )

    elif request.POST and cancellation_fee_form.is_valid():
        percentage = cancellation_fee_form.cleaned_data["percentage"]
        invoice = current_note.cancellation_fee(percentage)
        messages.success(
            request,
            "Generated cancellation fee for credit note %d." % note_id,
        )
        return redirect("invoice", invoice.invoice.id)

    data = {
        "credit_note": current_note.credit_note,
        "apply_form": apply_form,
        "refund_form": refund_form,
        "cancellation_fee_form": cancellation_fee_form,
    }

    return render(request, "registrasion/credit_note.html", data)


@user_passes_test(_staff_only)
def amend_registration(request, user_id):
    ''' Allows staff to amend a user's current registration cart, and etc etc.
    '''

    user = User.objects.get(id=int(user_id))
    current_cart = CartController.for_user(user)

    items = commerce.ProductItem.objects.filter(
        cart=current_cart.cart,
    ).select_related("product")
    initial = [{"product": i.product, "quantity": i.quantity, "price_override": i.price_override} for i in items]

    line_items = commerce.LineItem.objects.filter(
        invoice__user_id=user.id, invoice__status=commerce.Invoice.STATUS_PAID, cancelled=False,
    )

    StaffProductsFormSet = forms.staff_products_formset_factory(user)
    formset = StaffProductsFormSet(
        request.POST or None,
        initial=initial,
        prefix="products",
    )
    helper = FormHelper()
    helper.form_tag = False

    for item, form in zip(items, formset):
        queryset = inventory.Product.objects.filter(id=item.product.id)
        form.fields["product"].queryset = queryset

    voucher_form = forms.VoucherForm(
        request.POST or None,
        prefix="voucher",
    )

    if request.POST and voucher_form.has_changed() and voucher_form.is_valid():
        try:
            current_cart.apply_voucher(voucher_form.cleaned_data["voucher"])
            return redirect(amend_registration, user_id)
        except ValidationError as ve:
            voucher_form.add_error(None, ve)

    if request.POST and formset.is_valid():

        pq = [
            (f.cleaned_data["product"], f.cleaned_data["quantity"], f.cleaned_data["price_override"], None)
            for f in formset
            if "product" in f.cleaned_data and
            f.cleaned_data["product"] is not None
        ]

        try:
            current_cart.set_quantities(pq)
            return redirect(amend_registration, user_id)
        except ValidationError as ve:
            for ve_field in ve.error_list:
                product, message = ve_field.message
                for form in formset:
                    if "product" not in form.cleaned_data:
                        # This is the empty form.
                        continue
                    if form.cleaned_data["product"] == product:
                        form.add_error("quantity", message)

    ic = ItemController(user)
    data = {
        "user": user,
        "paid": ic.items_purchased(),
        "line_items": line_items.all(),
        "cancelled": ic.items_released(),
        "form": formset,
        "helper": helper,
        "active_vouchers": current_cart.cart.vouchers.all(),
        "voucher_form": voucher_form,
    }

    return render(request, "registrasion/amend_registration.html", data)


def _cancel_line_items(line_items, retain_discounts=False, cancellation_fee=0):
    items = []
    discounts = set()
    for line_item in line_items:
        line_item_discount = commerce.LineItem.objects.filter(invoice=line_item.invoice, product=line_item.product, price__lt=0, is_refund=False, cancelled=False).all()
        for discount in line_item_discount:
            discounts.add(discount)
    for line_item in line_items:
        line_item.cancelled = True
        if line_item.product is not None:
            product_items = commerce.ProductItem.objects.filter(
                cart__id=line_item.invoice.cart.id,
                product__id=line_item.product.id,
            )
            if len(product_items) == 1:
                product_item = product_items.first()
                product_item.quantity -= line_item.quantity
                product_item.save()
            else:
                for product_item in product_items.all():
                    if product_item.additional_data == line_item.additional_data:
                        product_item.quantity -= line_item.quantity
                        product_item.save()
        line_item.save()
        preamble = "Cancellation"
        if line_item.price > 0:
            preamble = "Refund"
        amount = 0-line_item.price
        if line_item.product is not None and line_item.product.is_donation:
            preamble = "Cancellation - Non-refundable"
            amount = 0
        items.append((f'{preamble}: {line_item.description}', amount, line_item.quantity))
    if not retain_discounts:
        for discount in discounts:
            discount.cancelled = True
            discount.save()
            preamble = "Discount removed"
            amount = 0-discount.price
            items.append((f'{preamble}: {discount.description}', amount, discount.quantity))
    if cancellation_fee > 0:
        items.append(("Cancellation Fee", cancellation_fee, 1))
    return items


@user_passes_test(_staff_only)
@transaction.atomic
def substitute_products(request, user_id):
    user = User.objects.get(id=int(user_id))
    line_items = commerce.LineItem.objects.filter(
        invoice__user_id=user.id, invoice__status=commerce.Invoice.STATUS_PAID, cancelled=False, is_refund=False, product__isnull=False, price__gte=0,
    )
    initial = [{"line_item_id": i.id, "product": i.product, "quantity": i.quantity, "price": i.price} for i in line_items]

    SubstituteProductsFormset = forms.substitute_products_formset_factory(user)
    formset = SubstituteProductsFormset(
        request.POST or None,
        initial=initial,
    )

    for item, form in zip(line_items, formset):
        queryset = inventory.Product.objects.filter(category=item.product.category)
        form.fields["product"].queryset = queryset

    if request.POST and formset.is_valid():
        items_to_cancel = []
        products_to_add = []
        for form in formset:
            line_item = commerce.LineItem.objects.get(id=form.cleaned_data["line_item_id"])
            if line_item.quantity != form.cleaned_data["quantity"] or line_item.product != form.cleaned_data["product"]:
                if line_item.quantity == 0 or form.cleaned_data["product"] is None:
                    items_to_cancel.append(line_item)
                if line_item.product != form.cleaned_data["product"] and form.cleaned_data["product"] is not None:
                    items_to_cancel.append(line_item)
                    price_override = None
                    if form.cleaned_data["product"].is_donation:
                        price_override = 0
                    products_to_add.append((form.cleaned_data["product"], form.cleaned_data["quantity"], price_override, None))
        if items_to_cancel:
            cancelled_items = _cancel_line_items(items_to_cancel, retain_discounts=True)
        else:
            cancelled_items = []
        invoice = None
        if products_to_add:
            cart = CartController.for_user(user)
            cart.empty_cart()
            for p in products_to_add:
                cart.set_quantities(products_to_add, enforce_limits=False)
            commerce.DiscountItem.objects.filter(cart=cart.cart).delete()
            invoice = InvoiceController.for_cart(cart.cart, additional_items=cancelled_items, validate=False).invoice
        else:
            invoice = InvoiceController.manual_invoice(
                user, datetime.timedelta(), cancelled_items
            )
        return redirect("invoice", invoice.id)

    data = {
        "user": user,
        "formset": formset,
        "items": line_items,
    }
    return render(request, "registrasion/substitute_products.html", data)


@user_passes_test(_staff_only)
@transaction.atomic
def cancel_line_items(request, user_id):

    user = User.objects.get(id=int(user_id))
    line_items = commerce.LineItem.objects.filter(
        invoice__user_id=user.id, invoice__status=commerce.Invoice.STATUS_PAID, cancelled=False, is_refund=False, product__isnull=False, price__gte=0,
    )

    form = forms.CancelLineItemsForm(user_id, request.POST or None)
    form.fields['line_items'].choices = [(li.id, li) for li in line_items.all()]

    if request.POST and form.is_valid():
        line_items = commerce.LineItem.objects.filter(id__in=form.cleaned_data['line_items']).all()
        items = _cancel_line_items(line_items, cancellation_fee=form.cleaned_data['cancellation_fee'])
        invoice = InvoiceController.manual_invoice(
            user, datetime.timedelta(), items
        )
        return redirect("invoice", invoice.id)

    data = {
        "user": user,
        "cancel_line_items_form": form
    }
    return render(request, "registrasion/cancel_line_items.html", data)

from registripe.views import process_refund
from registripe.models import StripePayment
class MockForm(object):
    def __init__(self, payment):
        self.cleaned_data = {}
        self.cleaned_data["payment"] = payment

@user_passes_test(_staff_only)
@transaction.atomic
def cancel_and_refund(request, user_id):

    user = User.objects.get(id=int(user_id))
    groups = []
    invoices = commerce.Invoice.objects.filter(
        user=user, status=commerce.Invoice.STATUS_PAID
    )
    all_payments = []
    all_stripe_payments = []
    for invoice in invoices:
        line_items = commerce.LineItem.objects.filter(
            invoice=invoice, cancelled=False, is_refund=False, product__isnull=False, price__gte=0,
        )
        payments = commerce.PaymentBase.objects.filter(
            invoice=invoice
        )
        for payment in payments:
            all_payments.append(payment)
        stripe_payments = StripePayment.objects.filter(
            invoice=invoice
        )
        for payment in stripe_payments:
            all_stripe_payments.append(payment)
        if line_items:
            groups.append({'invoice': invoice, 'line_items': line_items, 'payments': payments, 'stripe_payments': stripe_payments})

    hotel_reservations = user.attendee.hotelreservation_set.filter(status__in=['new', 'accepted', 'request'])

    form = forms.CancelForm(user_id, request.POST or None)

    if request.POST and form.is_valid():
        credit_notes = []
        payments = []
        for group in groups:
            items = _cancel_line_items(group['line_items'], cancellation_fee=0)
            invoice = InvoiceController.manual_invoice(user, datetime.timedelta(), items)
            InvoiceController(invoice).update_status()
            for payment in group['stripe_payments']:
                payments.append(payment)
            credit_note = commerce.CreditNote.objects.filter(invoice=invoice).first()
            if credit_note:
                credit_notes.append(credit_note)

        for credit_note, payment in zip(sorted(credit_notes, key=lambda cn: cn.amount, reverse=True), sorted(payments, key=lambda p: p.amount)):
            process_refund(CreditNoteController(credit_note), MockForm(payment))

        return redirect("attendee", user.id)

    data = {
        "user": user,
        "groups": groups,
        "hotel_reservations": hotel_reservations,
        "form": form,
        "processable": set([p.id for p in all_payments]) == set([p.id for p in all_stripe_payments]),
    }
    return render(request, "registrasion/cancel_and_refund.html", data)



@user_passes_test(_staff_only)
@transaction.atomic
def transfer_registration(request, user_id):

    user = User.objects.get(id=int(user_id))
    attendees = people.Attendee.objects.filter(attendeeprofilebase__isnull=False).filter(completed_registration=False)

    form = forms.TransferRegistrationForm(user_id, request.POST or None)
    form.fields['attendee'].choices = [(None, "---------")] + sorted([(a.user.id, a) for a in attendees], key=lambda x: str(x[1]))

    if request.POST and form.is_valid():
        new_user_id = form.cleaned_data['attendee']
        new_user = User.objects.get(id=int(new_user_id))
        attendee = people.Attendee.objects.get(user=new_user)
        carts = commerce.Cart.objects.filter(user=user)
        invoices = commerce.Invoice.objects.filter(user=user)
        last_invoice = invoices.order_by("-id").first()

        existing_carts = commerce.Cart.objects.filter(user=new_user)
        existing_invoices = commerce.Invoice.objects.filter(user=new_user)

        if any([c.status == commerce.Cart.STATUS_PAID for c in existing_carts]):
            form.add_error(None, "Cannot transfer to attendee with paid invoices or carts!")

        if any([i.status in [commerce.Invoice.STATUS_PAID, commerce.Invoice.STATUS_REFUNDED] for i in existing_invoices]):
            form.add_error(None, "Cannot transfer to attendee with paid invoices or carts!")

        if form.errors:
            pass
        else:
            existing_carts.delete()
            existing_invoices.delete()

            for invoice in invoices:
                invoice.user = new_user
                invoice.save()
            for cart in carts:
                cart.user = new_user
                cart.save()

            transfer_line_item = commerce.LineItem(
                invoice=last_invoice,
                description=f"Registration transferred from {user.email}",
                quantity=1,
                price=0,
            )
            transfer_line_item.save()
            new_user.attendee.completed_registration = True
            new_user.attendee.save()
            user.attendee.completed_registration = False
            user.attendee.save()

            return redirect("attendee", new_user_id)

    data = {
        "user": user,
        "form": form,
    }
    return render(request, "registrasion/transfer_registration.html", data)


@user_passes_test(_staff_only)
def extend_reservation(request, user_id, days=7):
    ''' Allows staff to extend the reservation on a given user's cart.
    '''

    user = User.objects.get(id=int(user_id))
    cart = CartController.for_user(user)
    cart.extend_reservation(datetime.timedelta(days=days))

    return redirect(request.META["HTTP_REFERER"])


Email = namedtuple(
    "Email",
    ("subject", "body", "from_email", "recipient_list"),
)


@user_passes_test(_staff_only)
def invoice_mailout(request):
    ''' Allows staff to send emails to users based on their invoice status. '''

    category = request.GET.getlist("category", [])
    product = request.GET.getlist("product", [])
    status = request.GET.get("status")

    form = forms.InvoiceEmailForm(
        request.POST or None,
        category=category,
        product=product,
        status=status,
    )

    emails = []

    if form.is_valid():
        emails = []
        for invoice in form.cleaned_data["invoice"]:
            # datatuple = (subject, message, from_email, recipient_list)
            from_email = form.cleaned_data["from_email"]
            subject = form.cleaned_data["subject"]
            body = Template(form.cleaned_data["body"]).render(
                Context({
                    "invoice": invoice,
                    "user": invoice.user,
                })
            )
            recipient_list = [invoice.user.email]
            emails.append(Email(subject, body, from_email, recipient_list))

        if form.cleaned_data["action"] == forms.InvoiceEmailForm.ACTION_SEND:
            # Send e-mails *ONLY* if we're sending.
            send_mass_mail(emails)
            messages.info(request, "The e-mails have been sent.")

    data = {
        "form": form,
        "emails": emails,
    }

    return render(request, "registrasion/invoice_mailout.html", data)


@user_passes_test(_staff_only)
def badge(request, user_id):
    ''' Renders a single user's badge (SVG). '''

    user_id = int(user_id)
    user = User.objects.get(pk=user_id)

    rendered = render_badge(user)
    response = HttpResponse(rendered)

    response["Content-Type"] = "image/svg+xml"
    response["Content-Disposition"] = 'inline; filename="badge.svg"'
    return response


@user_passes_test(_staff_only)
def badges(request):
    ''' Either displays a form containing a list of users with badges to
    render, or returns a .zip file containing their badges. '''

    category = request.GET.getlist("category", [])
    product = request.GET.getlist("product", [])
    status = request.GET.get("status")

    form = forms.InvoicesWithProductAndStatusForm(
        request.POST or None,
        category=category,
        product=product,
        status=status,
    )

    if form.is_valid():
        response = HttpResponse()
        response["Content-Type"] = "application.zip"
        response["Content-Disposition"] = 'attachment; filename="badges.zip"'

        z = zipfile.ZipFile(response, "w")

        for invoice in form.cleaned_data["invoice"]:
            user = invoice.user
            badge = render_badge(user)
            z.writestr("badge_%d.svg" % user.id, badge.encode("utf-8"))

        return response

    data = {
        "form": form,
    }

    return render(request, "registrasion/badges.html", data)


@user_passes_test(_staff_only)
def render_badge(user):
    ''' Renders a single user's badge. '''

    data = {
        "user": user,
    }

    t = loader.get_template('registrasion/badge.svg')
    return t.render(data)

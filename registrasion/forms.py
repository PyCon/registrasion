import collections

from .controllers.product import ProductController
from .models import commerce
from .models import inventory
from . import util

from django import forms
from django.conf import settings
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse

from crispy_forms.helper import FormHelper
from crispy_forms.layout import LayoutObject, Layout, Field, Fieldset, Div, HTML, ButtonHolder, Submit, TEMPLATE_PACK


def get_form_class_from_settings(config_name, default):
    import_path = getattr(settings, config_name, "")
    try:
        return util.get_object_from_name(import_path)
    except:
        return default


class ApplyCreditNoteForm(forms.Form):

    required_css_class = 'label-required'

    def __init__(self, user, *a, **k):
        ''' User: The user whose invoices should be made available as
        choices. '''
        self.user = user
        super(ApplyCreditNoteForm, self).__init__(*a, **k)
        self.helper = FormHelper()
        self.helper.form_method = "POST"
        self.helper.add_input(Submit('submit', 'Apply to invoice', css_class="btn-primary"))

        self.fields["invoice"].choices = self._unpaid_invoices

    def _unpaid_invoices(self):
        invoices = commerce.Invoice.objects.filter(
            status=commerce.Invoice.STATUS_UNPAID,
        ).select_related("user")

        invoices_annotated = [invoice.__dict__ for invoice in invoices]
        users = dict((inv.user.id, inv.user) for inv in invoices)
        for invoice in invoices_annotated:
            invoice.update({
                "user_id": users[invoice["user_id"]].id,
                "user_email": users[invoice["user_id"]].email,
            })

        key = lambda inv: (0 - (inv["user_id"] == self.user.id), inv["id"])  # noqa
        invoices_annotated.sort(key=key)

        template = (
            'Invoice %(id)d - user: %(user_email)s (%(user_id)d) '
            '-  $%(value)d'
        )
        return [
            (invoice["id"], template % invoice)
            for invoice in invoices_annotated
        ]

    invoice = forms.ChoiceField(
        required=True,
    )
    verify = forms.BooleanField(
        required=True,
        help_text="Have you verified that this is the correct invoice?",
    )


class CancelForm(forms.Form):
    def __init__(self, user_id, *a, **k):
        super(CancelForm, self).__init__(*a, **k)
        self.helper = FormHelper()
        self.helper.form_method = "POST"
        self.helper.form_action = reverse("cancel_and_refund", args=[user_id])
        self.helper.add_input(Submit('submit', 'Cancel And Refund', css_class="btn-primary"))


class CancelLineItemsForm(forms.Form):

    required_css_class = 'label-required'

    def __init__(self, user_id, *a, **k):
        super(CancelLineItemsForm, self).__init__(*a, **k)
        self.helper = FormHelper()
        self.helper.form_method = "POST"
        self.helper.form_action = reverse("cancel_line_items", args=[user_id])
        self.helper.add_input(Submit('submit', 'Cancel Line Items', css_class="btn-primary"))

    line_items = forms.MultipleChoiceField(
        label="Line Items to Cancel",
        widget=forms.CheckboxSelectMultiple,
    )

    cancellation_fee = forms.DecimalField()


class TransferRegistrationForm(forms.Form):

    required_css_class = 'label-required'

    def __init__(self, user_id, *a, **k):
        super(TransferRegistrationForm, self).__init__(*a, **k)
        self.helper = FormHelper()
        self.helper.form_method = "POST"
        self.helper.form_action = reverse("transfer_registration", args=[user_id])
        self.helper.add_input(Submit('submit', 'Transfer Registration', css_class="btn-primary"))

    attendee = forms.ChoiceField(
        label="Attendee to transfer to",
        widget=forms.Select,
    )


class CancellationFeeForm(forms.Form):

    required_css_class = 'label-required'

    def __init__(self, *a, **k):
        super(CancellationFeeForm, self).__init__(*a, **k)
        self.helper = FormHelper()
        self.helper.form_method = "POST"
        self.helper.add_input(Submit('submit', 'Generate fee', css_class="btn-primary"))

    percentage = forms.DecimalField(
        required=True,
        min_value=0,
        max_value=100,
    )


class ManualCreditNoteRefundForm(forms.ModelForm):

    required_css_class = 'label-required'

    def __init__(self, *a, **k):
        super(ManualCreditNoteRefundForm, self).__init__(*a, **k)
        self.helper = FormHelper()
        self.helper.form_method = "POST"
        self.helper.add_input(Submit('submit', 'Mark as refunded', css_class="btn-primary"))

    class Meta:
        model = commerce.ManualCreditNoteRefund
        fields = ["reference"]


class ManualPaymentForm(forms.ModelForm):

    required_css_class = 'label-required'

    def __init__(self, *a, **k):
        super(ManualPaymentForm, self).__init__(*a, **k)
        self.helper = FormHelper()
        self.helper.form_method = "POST"
        self.helper.add_input(Submit('submit', 'Apply Payment', css_class="btn-primary"))

    class Meta:
        model = commerce.ManualPayment
        fields = ["reference", "amount"]


# Products forms -- none of these have any fields: they are to be subclassed
# and the fields added as needs be. ProductsForm (the function) is responsible
# for the subclassing.

def ProductsForm(category, products, sold_out_products=None, disabled_products=None):
    ''' Produces an appropriate _ProductsForm subclass for the given render
    type. '''

    # Each Category.RENDER_TYPE value has a subclass here.
    cat = inventory.Category
    RENDER_TYPES = {
        cat.RENDER_TYPE_QUANTITY: get_form_class_from_settings(
            "REGISTRASION_QUANTITY_BOX_PRODUCTS_FORM", _QuantityBoxProductsForm),
        cat.RENDER_TYPE_RADIO: get_form_class_from_settings(
            "REGISTRASION_RADIO_BUTTON_PRODUCTS_FORM", _RadioButtonProductsForm),
        cat.RENDER_TYPE_ITEM_QUANTITY: get_form_class_from_settings(
            "REGISTRASION_ITEM_QUANTITY_PRODUCTS_FORM", _ItemQuantityProductsForm),
        cat.RENDER_TYPE_CHECKBOX: get_form_class_from_settings(
            "REGISTRASION_CHECKBOX_PRODUCTS_FORM", _CheckboxProductsForm),
        cat.RENDER_TYPE_PWYW: get_form_class_from_settings(
            "REGISTRASION_PAY_WHAT_YOU_WANT_PRODUCTS_FORM", _PayWhatYouWantProductsForm),
        cat.RENDER_TYPE_PWYW_QUANTITY: get_form_class_from_settings(
            "REGISTRASION_PAY_WHAT_YOU_WANT_WITH_QUANTITY_PRODUCTS_FORM", _PayWhatYouWantWithQuantityProductsForm),
        cat.RENDER_TYPE_CHECKBOX_QUANTITY: get_form_class_from_settings(
            "REGISTRASION_CHECKBOX_FOR_LIMIT_ONE_PRODUCTS_FORM", _CheckboxForLimitOneProductsForm),
        cat.RENDER_TYPE_CHILDCARE: get_form_class_from_settings(
            "REGISTRASION_CHILDCARE_PRODUCTS_FORM", _ChildcareProductsForm),
        cat.RENDER_TYPE_YOUNGCODERS: get_form_class_from_settings(
            "REGISTRASION_YOUNG_CODERS_PRODUCTS_FORM", _YoungCodersProductsForm),
        cat.RENDER_TYPE_PRESENTATION: get_form_class_from_settings(
            "REGISTRASION_PRESENTATION_PRODUCTS_FORM", _PresentationProductsForm),
    }

    # Produce a subclass of _ProductsForm which we can alter the base_fields on
    class ProductsForm(RENDER_TYPES[category.render_type]):
        helper = FormHelper()
        helper.form_tag = False

        def __init__(self, *args, **kwargs):
            super(ProductsForm, self).__init__(*args, **kwargs)

    products = list(products)
    products.sort(key=lambda prod: prod.order)
    if sold_out_products is None:
        sold_out_products = []
    else:
        sold_out_products = list(sold_out_products)
        sold_out_products.sort(key=lambda prod: prod.order)

    if disabled_products is None:
        disabled_products = {}

    ProductsForm.set_fields(category, products, sold_out_products, disabled_products)

    if category.render_type == inventory.Category.RENDER_TYPE_ITEM_QUANTITY:
        ProductsForm = forms.formset_factory(
            ProductsForm,
            formset=_ItemQuantityProductsFormSet,
        )

    return ProductsForm


class _HasProductsFields(object):

    PRODUCT_PREFIX = "product_"
    PRICE_PREFIX = "price_"

    ''' Base class for product entry forms. '''
    def __init__(self, *a, **k):
        if "product_quantities" in k:
            initial = self.initial_data(k["product_quantities"])
            k["initial"] = initial
            del k["product_quantities"]
        super(_HasProductsFields, self).__init__(*a, **k)

    @classmethod
    def field_name(cls, product):
        return cls.PRODUCT_PREFIX + ("%d" % product.id)

    @classmethod
    def price_field_name(cls, product):
        return cls.PRICE_PREFIX + ("%d" % product.id)

    @classmethod
    def set_fields(cls, category, products):
        ''' Sets the base_fields on this _ProductsForm to allow selecting
        from the provided products. '''
        pass

    @classmethod
    def initial_data(cls, product_quantites):
        ''' Prepares initial data for an instance of this form.
        product_quantities is a sequence of (product,quantity,price_override) tuples '''
        return {}

    @property
    def contains_errors(self):
        return True if self.errors else False

    def product_quantities(self):
        ''' Yields a sequence of (product, quantity, price_override, additional_data) tuples from the
        cleaned form data. '''
        return iter([])

    def add_product_error(self, product, error):
        ''' Adds an error to the given product's field '''

        ''' if product in field_names:
            field = field_names[product]
        elif isinstance(product, inventory.Product):
            return
        else:
            field = None '''

        self.add_error(self.field_name(product), error)


class _ProductsForm(_HasProductsFields, forms.Form):

    required_css_class = 'label-required'

    pass


class _QuantityBoxProductsForm(_ProductsForm):
    ''' Products entry form that allows users to enter quantities
    of desired products. '''

    @classmethod
    def set_fields(cls, category, products, sold_out_products, disabled_products):
        for product in products:
            if product.description:
                if product.display_price:
                    help_text = "$%d each -- %s" % (
                        product.price,
                        product.description,
                    )
                else:
                    help_text = product.description
            else:
                if product.display_price:
                    help_text = "$%d each" % product.price
                else:
                    help_text = None

            field = forms.IntegerField(
                label=product.name,
                help_text=help_text,
                min_value=0,
                max_value=500,  # Issue #19. We should figure out real limit.
            )
            cls.base_fields[cls.field_name(product)] = field

        layout_objects = []
        for product in products:
            layout_objects.append(
                Div(
                    cls.field_name(product),
                    css_class=category.product_css_class if category.product_css_class else "",
                )
            )
        if len(sold_out_products) > 0:
            html = "<h3>Sold Out:</h3>\n"
            html += "<ul>\n"
            for product in sold_out_products:
                html += f"<li>{product.name}</li>\n"
            html += "</ul>"
            layout_objects.append(Div(HTML(html)))
        cls.helper.layout = Layout(
            Div(
                *layout_objects,
                css_class=category.form_css_class if category.form_css_class else "",
            )
        )

    @classmethod
    def initial_data(cls, product_quantities):
        initial = {}
        for product, quantity, _, _ in product_quantities:
            initial[cls.field_name(product)] = quantity

        return initial

    def product_quantities(self):
        for name, value in self.cleaned_data.items():
            if name.startswith(self.PRODUCT_PREFIX):
                product_id = int(name[len(self.PRODUCT_PREFIX):])
                yield (product_id, value, None, None)


class _RadioButtonProductsForm(_ProductsForm):
    ''' Products entry form that allows users to enter quantities
    of desired products. '''

    FIELD = "chosen_product"

    @classmethod
    def set_fields(cls, category, products, sold_out_products, disabled_products):
        choices = []
        for product in products:
            if product.display_price:
                choice_text = "%s -- $%d" % (product.name, product.price)
            else:
                choice_text = product.name
            choices.append((product.id, choice_text))

        if not category.required:
            choices.append((0, "No selection"))

        cls.base_fields[cls.FIELD] = forms.TypedChoiceField(
            label=category.name,
            widget=forms.RadioSelect,
            choices=choices,
            empty_value=0,
            coerce=int,
        )

        layout_objects = []
        layout_objects.append(
            Div(
                cls.FIELD,
                css_class=category.product_css_class if category.product_css_class else "",
            )
        )
        if len(sold_out_products) > 0:
            html = "<h3>Sold Out:</h3>\n"
            html += "<ul>\n"
            for product in sold_out_products:
                html += f"<li>{product.name}</li>\n"
            html += "</ul>"
            layout_objects.append(Div(HTML(html)))

        cls.helper.layout = Layout(
            Div(
                *layout_objects,
                css_class=category.form_css_class if category.form_css_class else "",
            )
        )

    @classmethod
    def initial_data(cls, product_quantities):
        initial = {}

        for product, quantity, _, _ in product_quantities:
            if quantity > 0:
                initial[cls.FIELD] = product.id
                break
            else:
                initial[cls.FIELD] = 0

        return initial

    def product_quantities(self):
        ours = self.cleaned_data[self.FIELD]
        choices = self.fields[self.FIELD].choices
        for choice_value, choice_display in choices:
            if choice_value == 0:
                continue
            yield (
                choice_value,
                1 if ours == choice_value else 0,
                None,
                None,
            )

    def add_product_error(self, product, error):
        self.add_error(self.FIELD, error)


class _CheckboxProductsForm(_ProductsForm):
    ''' Products entry form that allows users to say yes or no
    to desired products. Basically, it's a quantity form, but the quantity
    is either zero or one.'''

    @classmethod
    def set_fields(cls, category, products, sold_out_products, disabled_products):
        for product in products:
            field = forms.BooleanField(
                label='%s -- %s' % (product.name, product.price),
                required=False,
            )
            cls.base_fields[cls.field_name(product)] = field

        layout_objects = []
        for product in products:
            layout_objects.append(
                Div(
                    cls.field_name(product),
                    css_class=category.product_css_class if category.product_css_class else "",
                )
            )
        cls.helper.layout = Layout(
            Div(
                *layout_objects,
                css_class=category.form_css_class if category.form_css_class else "",
            )
        )

    @classmethod
    def initial_data(cls, product_quantities):
        initial = {}
        for product, quantity, _, _ in product_quantities:
            initial[cls.field_name(product)] = bool(quantity)

        return initial

    def product_quantities(self):
        for name, value in self.cleaned_data.items():
            if name.startswith(self.PRODUCT_PREFIX):
                product_id = int(name[len(self.PRODUCT_PREFIX):])
                yield (product_id, int(value), None, None)


class LayoutFormset(LayoutObject):
    """
    Renders an entire formset, as though it were a Field.
    Accepts the names (as a string) of formset and helper as they
    are defined in the context

    Examples:
        Formset(formset)
        Formset(formset, helper)
    """

    template = "forms/formset.html"

    def __init__(self, formset, helper=None, template=None, label=None):

        self.formset = formset
        self.helper = helper

        # crispy_forms/layout.py:302 requires us to have a fields property
        self.fields = []

        # Overrides class variable with an instance level variable
        if template:
            self.template = template

    def render(self, form, form_style, context, **kwargs):
        formset = self.formset
        helper = self.helper
        # closes form prematurely if this isn't explicitly stated
        if helper:
            helper.form_tag = False

        context.update({'formset': formset, 'helper': helper})
        return render_to_string(self.template, context.flatten())


class _ChildForm(forms.Form):

    def __init__(self, *args, **kwargs):
        self.helper = helper = FormHelper()
        self.helper.disable_csrf = True
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Div(
                Div(
                    'dates',
                    css_class="registration-side-by-side",
                ),
                Div(
                    'child_first_name',
                    'child_last_name',
                    'child_age',
                    css_class="registration-side-by-side",
                ),
                'child_needs',
                Div(
                    Div(
                        'emergency_contact_1_first_name',
                        'emergency_contact_1_last_name',
                        'emergency_contact_1_phone',
                        css_class="registration-side-by-side",
                    ),
                    Div(
                        'emergency_contact_2_first_name',
                        'emergency_contact_2_last_name',
                        'emergency_contact_2_phone',
                        css_class="registration-side-by-side",
                    ),
                ),
                css_class="childcare-child-form",
            )
        )
        super(_ChildForm, self).__init__(*args, **kwargs)

    dates = forms.MultipleChoiceField(
        label='Select Dates',
        choices=(),
        widget=forms.CheckboxSelectMultiple(),
    )

    child_first_name = forms.CharField(
        label='Child\'s First Name',
    )
    child_last_name = forms.CharField(
        label='Child\'s Last Name',
    )
    child_age = forms.CharField(
        label='Child\'s Age',
    )

    child_needs = forms.CharField(
        label='Special Instructions/Needs',
        required=False,
    )

    emergency_contact_1_first_name = forms.CharField(
        label='Emergency Contact 1 First Name',
    )
    emergency_contact_1_last_name = forms.CharField(
        label='Emergency Contact 1 Last Name',
    )
    emergency_contact_1_phone = forms.CharField(
        label='Emergency Contact 1 Phone',
    )

    emergency_contact_2_first_name = forms.CharField(
        label='Emergency Contact 2 First Name',
    )
    emergency_contact_2_last_name = forms.CharField(
        label='Emergency Contact 2 Last Name',
    )
    emergency_contact_2_phone = forms.CharField(
        label='Emergency Contact 2 Phone',
    )

_ChildFormSet = forms.formset_factory(_ChildForm, extra=1)


class _ChildcareProductsForm(_ProductsForm):

    PRODUCT_ID = None
    PRODUCT_PRICE = 0
    DATES_CHOICES = []
    FORMSET = _ChildFormSet

    def __init__(self, *args, **kwargs):
        initial = self.initial_data(kwargs["product_quantities"])
        self.formset = _ChildFormSet(args[0], prefix=f'product_{self.PRODUCT_ID}', initial=initial)
        self.formset.form.base_fields['dates'].choices=self.DATES_CHOICES

        layout_objects = [
            LayoutFormset(self.formset)
        ]

        self.helper.layout = Layout(
            Div(
                *layout_objects,
            )
        )

        super(_ChildcareProductsForm, self).__init__(*args, **kwargs)

    @classmethod
    def set_fields(cls, category, products, sold_out_products, disabled_products):
        for i, product in enumerate(products):
            cls.PRODUCT_ID = product.id
            cls.PRODUCT_PRICE = product.price
            cls.DATES_CHOICES = product.additional_data['available_dates']

    def is_valid(self, *args, **kwargs):
        return (super(_ChildcareProductsForm, self).is_valid() and self.formset.is_valid())

    def has_changed(self, *args, **kwargs):
        return (
            super(_ChildcareProductsForm, self).has_changed()
            or any([f.has_changed() for f in self.formset.forms])
            or len(self.formset.forms) == 0
        )

    @property
    def contains_errors(self):
        return True if self.errors or any(self.formset.errors) else False

    @classmethod
    def initial_data(cls, product_quantities):
        initial = []
        for product, quantity, _, additional_data in product_quantities:
            if quantity > 0:
                initial.append({
                    'dates': additional_data['dates'],
                    'child_first_name': additional_data['child_first_name'],
                    'child_last_name': additional_data['child_last_name'],
                    'child_age': additional_data['child_age'],
                    'emergency_contact_1_first_name': additional_data['emergency_contact_1_first_name'],
                    'emergency_contact_1_last_name': additional_data['emergency_contact_1_last_name'],
                    'emergency_contact_1_phone': additional_data['emergency_contact_1_phone'],
                    'emergency_contact_2_first_name': additional_data['emergency_contact_2_first_name'],
                    'emergency_contact_2_last_name': additional_data['emergency_contact_2_last_name'],
                    'emergency_contact_2_phone': additional_data['emergency_contact_2_phone'],
                })
        return initial

    def product_quantities(self):
        for item in self.formset.cleaned_data:
            if len(item.get('dates', [])) > 0:
                item['line_item_info'] = (
                    f'Child: {item["child_first_name"]} {item["child_last_name"]} '
                    f' - Dates: {", ".join(item["dates"])}'
                )
                if len(item['dates']) == 4:
                    item['adhoc_discount'] = {
                        'description': 'Childcare - 4th Day Free',
                        'price': int(self.PRODUCT_PRICE),
                        'line_item_info': (
                            f'Child: {item["child_first_name"]} {item["child_last_name"]} '
                            f' - Dates: {", ".join(item["dates"])}'
                        ),
                    }
                yield (self.PRODUCT_ID, len(item['dates']), None, item)
            else:
                yield (self.PRODUCT_ID, 0, None, {})
        else:
            yield (self.PRODUCT_ID, 0, None, {})


class _YoungCoderForm(forms.Form):

    def __init__(self, *args, **kwargs):
        self.helper = helper = FormHelper()
        self.helper.disable_csrf = True
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Div(
                Div(
                    'child_first_name',
                    'child_last_name',
                    'child_age',
                    css_class="registration-side-by-side",
                ),
                'child_needs',
                Div(
                    Div(
                        'emergency_contact_1_first_name',
                        'emergency_contact_1_last_name',
                        'emergency_contact_1_phone',
                        css_class="registration-side-by-side",
                    ),
                    Div(
                        'emergency_contact_2_first_name',
                        'emergency_contact_2_last_name',
                        'emergency_contact_2_phone',
                        css_class="registration-side-by-side",
                    ),
                ),
                css_class="childcare-child-form",
            )
        )
        super(_YoungCoderForm, self).__init__(*args, **kwargs)

    child_first_name = forms.CharField(
        label='Child\'s First Name',
    )
    child_last_name = forms.CharField(
        label='Child\'s Last Name',
    )
    child_age = forms.CharField(
        label='Child\'s Age',
    )
    child_needs = forms.CharField(
        label='Special Instructions/Needs',
        required=False,
    )

    emergency_contact_1_first_name = forms.CharField(
        label='Emergency Contact 1 First Name',
    )
    emergency_contact_1_last_name = forms.CharField(
        label='Emergency Contact 1 Last Name',
    )
    emergency_contact_1_phone = forms.CharField(
        label='Emergency Contact 1 Phone',
    )

    emergency_contact_2_first_name = forms.CharField(
        label='Emergency Contact 2 First Name',
    )
    emergency_contact_2_last_name = forms.CharField(
        label='Emergency Contact 2 Last Name',
    )
    emergency_contact_2_phone = forms.CharField(
        label='Emergency Contact 2 Phone',
    )

_YoungCoderFormSet = forms.formset_factory(_YoungCoderForm, extra=1)


class _YoungCodersProductsForm(_ProductsForm):

    DATES_CHOICES = []
    FORMSET = _YoungCoderFormSet
    PRODUCT_ID = None

    def __init__(self, *args, **kwargs):
        initial = self.initial_data(kwargs["product_quantities"])
        self.formset = _YoungCoderFormSet(args[0], prefix=f'product_{self.PRODUCT_ID}', initial=initial)

        layout_objects = [
            LayoutFormset(self.formset)
        ]

        self.helper.layout = Layout(
            Div(
                *layout_objects,
            )
        )

        super(_YoungCodersProductsForm, self).__init__(*args, **kwargs)

    @classmethod
    def set_fields(cls, category, products, sold_out_products, disabled_products):
        for i, product in enumerate(products):
            cls.PRODUCT_ID = product.id

    def is_valid(self, *args, **kwargs):
        return (super(_YoungCodersProductsForm, self).is_valid() and self.formset.is_valid())

    def has_changed(self, *args, **kwargs):
        return (
            super(_YoungCodersProductsForm, self).has_changed()
            or any([f.has_changed() for f in self.formset.forms])
            or len(self.formset.forms) == 0
        )

    @property
    def contains_errors(self):
        return True if self.errors or any(self.formset.errors) else False

    @classmethod
    def initial_data(cls, product_quantities):
        initial = []
        for product, quantity, _, additional_data in product_quantities:
            if quantity > 0:
                initial.append({
                    'child_first_name': additional_data['child_first_name'],
                    'child_last_name': additional_data['child_last_name'],
                    'child_age': additional_data['child_age'],
                    'emergency_contact_1_first_name': additional_data['emergency_contact_1_first_name'],
                    'emergency_contact_1_last_name': additional_data['emergency_contact_1_last_name'],
                    'emergency_contact_1_phone': additional_data['emergency_contact_1_phone'],
                    'emergency_contact_2_first_name': additional_data['emergency_contact_2_first_name'],
                    'emergency_contact_2_last_name': additional_data['emergency_contact_2_last_name'],
                    'emergency_contact_2_phone': additional_data['emergency_contact_2_phone'],
                })
        return initial

    def product_quantities(self):
        for item in self.formset.cleaned_data:
            item['line_item_info'] = f'Child: {item["child_first_name"]} {item["child_last_name"]}'
            yield (self.PRODUCT_ID, 1, None, item)
        else:
            yield (self.PRODUCT_ID, 0, None, {})


class _PayWhatYouWantProductsForm(_ProductsForm):
    ''' Products entry form that allows users to enter their own
    amount for products. '''

    @classmethod
    def set_fields(cls, category, products, sold_out_products, disabled_products):
        for product in products:
            if product.description:
                help_text = "Enter a donation amount in USD -- %s" % (
                    product.description,
                )
            else:
                help_text = "Enter a donation amount in USD"

            price_field = forms.DecimalField(
                label=product.name,
                help_text=help_text,
                min_value=0,
                required=False,
            )
            cls.base_fields[cls.price_field_name(product)] = price_field

        layout_objects = []
        for product in products:
            layout_objects.append(
                Div(
                    cls.price_field_name(product),
                    css_class=category.product_css_class if category.product_css_class else "",
                )
            )
        cls.helper.layout = Layout(
            Div(
                *layout_objects,
                css_class=category.form_css_class if category.form_css_class else "",
            )
        )

    @classmethod
    def initial_data(cls, product_quantities):
        initial = {}
        for product, _, price_override, _ in product_quantities:
            if price_override is None or int(price_override) == 0:
                initial[cls.price_field_name(product)] = 0
            else:
                initial[cls.price_field_name(product)] = price_override

        return initial

    def product_quantities(self):
        for name, value in self.cleaned_data.items():
            if name.startswith(self.PRICE_PREFIX):
                product_id = int(name[len(self.PRICE_PREFIX):])
                if value is not None and value > 0:
                    yield (product_id, 1, value, {})
                else:
                    yield (product_id, 0, None, {})

class _PayWhatYouWantWithQuantityProductsForm(_ProductsForm):
    ''' Products entry form that allows users to enter their own
    amount and quantity for products. '''

    @classmethod
    def set_fields(cls, category, products, sold_out_products, disabled_products):
        for product in products:
            if product.description:
                help_text = "Enter a donation amount (per item) in USD -- %s" % (
                    product.description,
                )
            else:
                help_text = "Enter a donation amount (per item) in USD"

            price_field = forms.DecimalField(
                label=product.name,
                help_text=help_text,
                min_value=0,
                required=False,
            )
            cls.base_fields[cls.price_field_name(product)] = price_field

            quantity_field = forms.IntegerField(
                label="",
                help_text="Quantity",
                min_value=0,
                max_value=500,
                required=False,
            )
            cls.base_fields[cls.field_name(product)] = quantity_field

        layout_objects = []
        for product in products:
            css_class = "pwywwq-group"
            if category.product_css_class:
                css_class += f" {category.product_css_class}"
            layout_objects.append(
                Div(
                    cls.price_field_name(product),
                    cls.field_name(product),
                    css_class=css_class,
                )
            )
        css_class = "pwywwq-grid"
        if category.form_css_class:
            css_class += f" {category.form_css_class}"
        cls.helper.layout = Layout(
            Div(
                *layout_objects,
                css_class=css_class,
            )
        )

    @classmethod
    def initial_data(cls, product_quantities):
        initial = {}
        for product, quantity, price_override, _ in product_quantities:
            if price_override is None or int(price_override) == 0:
                initial[cls.price_field_name(product)] = product.price
            else:
                initial[cls.price_field_name(product)] = price_override
            if quantity > 0:
                initial[cls.field_name(product)] = quantity
            else:
                initial[cls.field_name(product)] = 0

        return initial

    def product_quantities(self):
        for name, value in self.cleaned_data.items():
            if name.startswith(self.PRODUCT_PREFIX):
                product_id = int(name[len(self.PRODUCT_PREFIX):])
                product = inventory.Product.objects.get(pk=product_id)
                price = product.price
                if product.pay_what_you_want:
                    price = self.cleaned_data[self.price_field_name(product)]
                if value is None:
                    value = 0
                yield (product_id, value, price, {})

class _CheckboxForLimitOneProductsForm(_ProductsForm):
    @classmethod
    def set_fields(cls, category, products, sold_out_products, disabled_products):
        for product in products:
            if product.limit_per_user == 1:
                if product.price == 0.00:
                    if product.description:
                        help_text = "Included in registration -- %s" % (product.description,)
                    else:
                        help_text = "Included in registration"
                else:
                    help_text = "$%d" % (product.price)
                field = forms.BooleanField(
                    label='%s' % (product.name,),
                    help_text=help_text,
                    required=False,
                )
                cls.base_fields[cls.field_name(product)] = field
            else:
                if product.description:
                    help_text = "$%d each -- %s" % (
                        product.price,
                        product.description,
                    )
                else:
                    help_text = "$%d each" % product.price

                field = forms.IntegerField(
                    label=product.name,
                    help_text=help_text,
                    min_value=0,
                    max_value=500,  # Issue #19. We should figure out real limit.
                )
                cls.base_fields[cls.field_name(product)] = field

        layout_objects = []
        for product in products:
            layout_objects.append(
                Div(
                    cls.field_name(product),
                    css_class=category.product_css_class if category.product_css_class else "",
                )
            )
        if len(sold_out_products) > 0:
            html = "<h3>Sold Out:</h3>\n"
            html += "<ul>\n"
            for product in sold_out_products:
                html += f"<li>{product.name}</li>\n"
            html += "</ul>"
            layout_objects.append(Div(HTML(html)))
        cls.helper.layout = Layout(
            Div(
                *layout_objects,
                css_class=category.form_css_class if category.form_css_class else "",
            )
        )

    @classmethod
    def initial_data(cls, product_quantities):
        initial = {}
        for product, quantity, _, _ in product_quantities:
            if product.limit_per_user == 1:
                initial[cls.field_name(product)] = bool(quantity)
            else:
                initial[cls.field_name(product)] = quantity

        return initial

    def product_quantities(self):
        for name, value in self.cleaned_data.items():
            if name.startswith(self.PRODUCT_PREFIX):
                product_id = int(name[len(self.PRODUCT_PREFIX):])
                yield (product_id, int(value), None, None)

class _ItemQuantityProductsForm(_ProductsForm):
    ''' Products entry form that allows users to select a product type, and
     enter a quantity of that product. This version _only_ allows a single
     product type to be purchased. This form is usually used in concert with
     the _ItemQuantityProductsFormSet to allow selection of multiple
     products.'''

    CHOICE_FIELD = "choice"
    QUANTITY_FIELD = "quantity"

    @classmethod
    def set_fields(cls, category, products, sold_out_products, disabled_products):
        choices = []

        if not category.required:
            choices.append((0, "---"))

        for product in products:
            choice_text = "%s -- $%d each" % (product.name, product.price)
            choices.append((product.id, choice_text))

        cls.base_fields[cls.CHOICE_FIELD] = forms.TypedChoiceField(
            label=category.name,
            widget=forms.Select,
            choices=choices,
            initial=0,
            empty_value=0,
            coerce=int,
        )

        cls.base_fields[cls.QUANTITY_FIELD] = forms.IntegerField(
            label="Quantity",  # TODO: internationalise
            min_value=0,
            max_value=500,  # Issue #19. We should figure out real limit.
        )

    @classmethod
    def initial_data(cls, product_quantities):
        initial = {}

        for product, quantity, _, _ in product_quantities:
            if quantity > 0:
                initial[cls.CHOICE_FIELD] = product.id
                initial[cls.QUANTITY_FIELD] = quantity
                break

        return initial

    def product_quantities(self):
        our_choice = self.cleaned_data[self.CHOICE_FIELD]
        our_quantity = self.cleaned_data[self.QUANTITY_FIELD]
        choices = self.fields[self.CHOICE_FIELD].choices
        for choice_value, choice_display in choices:
            if choice_value == 0:
                continue
            yield (
                choice_value,
                our_quantity if our_choice == choice_value else 0,
                None,
                None,
            )

    def add_product_error(self, product, error):
        if self.CHOICE_FIELD not in self.cleaned_data:
            return

        if product.id == self.cleaned_data[self.CHOICE_FIELD]:
            self.add_error(self.CHOICE_FIELD, error)
            self.add_error(self.QUANTITY_FIELD, error)


class _ItemQuantityProductsFormSet(_HasProductsFields, forms.BaseFormSet):

    required_css_class = 'label-required'

    @classmethod
    def set_fields(cls, category, products, sold_out_products, disabled_products):
        raise ValueError("set_fields must be called on the underlying Form")

    @classmethod
    def initial_data(cls, product_quantities):
        ''' Prepares initial data for an instance of this form.
        product_quantities is a sequence of (product,quantity) tuples '''

        f = [
            {
                _ItemQuantityProductsForm.CHOICE_FIELD: product.id,
                _ItemQuantityProductsForm.QUANTITY_FIELD: quantity,
            }
            for product, quantity, _, _ in product_quantities
            if quantity > 0
        ]
        return f

    def product_quantities(self):
        ''' Yields a sequence of (product, quantity) tuples from the
        cleaned form data. '''

        products = set()
        # Track everything so that we can yield some zeroes
        all_products = set()

        for form in self:
            if form.empty_permitted and not form.cleaned_data:
                # This is the magical empty form at the end of the list.
                continue

            for product, quantity in form.product_quantities():
                all_products.add(product)
                if quantity == 0:
                    continue
                if product in products:
                    form.add_error(
                        _ItemQuantityProductsForm.CHOICE_FIELD,
                        "You may only choose each product type once.",
                    )
                    form.add_error(
                        _ItemQuantityProductsForm.QUANTITY_FIELD,
                        "You may only choose each product type once.",
                    )
                products.add(product)
                yield product, quantity, None

        for product in (all_products - products):
            yield product, 0, None, None

    def add_product_error(self, product, error):
        for form in self.forms:
            form.add_product_error(product, error)

    @property
    def errors(self):
        _errors = super(_ItemQuantityProductsFormSet, self).errors
        if False not in [not form.errors for form in self.forms]:
            return []
        else:
            return _errors


class _PresentationProductsForm(_ProductsForm):
    ''' Products entry form that allows users to say yes or no
    to desired products. Basically, it's a quantity form, but the quantity
    is either zero or one.'''

    @classmethod
    def set_fields(cls, category, products, sold_out_products, disabled_products):
        dates = set()
        sessions = set()
        products_by_date_by_session = collections.defaultdict(lambda: collections.defaultdict(list))
        for product in products:
            presentation_datetime = product.presentation.slot.start_datetime
            dates.add(presentation_datetime.date())
            sessions.add(presentation_datetime.time())
            products_by_date_by_session[presentation_datetime.date()][presentation_datetime.time()].append(product)
        sold_out_products_by_date_by_session = collections.defaultdict(lambda: collections.defaultdict(list))
        for product in sold_out_products:
            presentation_datetime = product.presentation.slot.start_datetime
            dates.add(presentation_datetime.date())
            sessions.add(presentation_datetime.time())
            sold_out_products_by_date_by_session[presentation_datetime.date()][presentation_datetime.time()].append(product)
        disabled_sessions = set((p.presentation.slot.start_datetime.date(), p.presentation.slot.start_datetime.time()) for p in disabled_products['purchased'])
        pending_sessions = set((p.presentation.slot.start_datetime.date(), p.presentation.slot.start_datetime.time()) for p in disabled_products['pending'])

        layout_objects = []
        for day in sorted(dates):
            session_objects = []
            for session in sorted(sessions):
                product_objects = []
                for product in products_by_date_by_session[day][session]:
                    if product in disabled_products['purchased']:
                        product_objects.append(
                            Div(
                                HTML(f"<p>{product.presentation.title}<br></p>"),
                                HTML(f'<p style="text-align: center; margin-bottom: 0em; font-size: smaller"><i>{", ".join([str(s) for s in product.presentation.speakers()])}</i></p>'),
                                css_class=f"session-{day}T{session.strftime('%H-%M')} {category.product_css_class} disabled" if category.product_css_class else "session-{day}T{session.strftime('%H-%M')} disabled",
                            )
                        )
                        continue
                    if product in disabled_products['pending']:
                        product_objects.append(
                            Div(
                                HTML(f"<p>{product.presentation.title}<br></p>"),
                                HTML(f'<p style="text-align: center; margin-bottom: 0em; font-size: smaller"><i>{", ".join([str(s) for s in product.presentation.speakers()])}</i></p>'),
                                css_class=f"session-{day}T{session.strftime('%H-%M')} {category.product_css_class} disabled" if category.product_css_class else "session-{day}T{session.strftime('%H-%M')} disabled",
                            )
                        )
                        continue
                    field = forms.BooleanField(
                        label='%s' % (product.presentation.title),
                        required=False,
                    )
                    cls.base_fields[cls.field_name(product)] = field
                    product_objects.append(
                        Div(
                            cls.field_name(product),
                            HTML(f'<br><p style="text-align: center; margin-bottom: 0em; font-size: smaller"><i>{", ".join([str(s) for s in product.presentation.speakers()])}</i></p>'),
                            css_class=f"session-{day}T{session.strftime('%H-%M')} {category.product_css_class}" if category.product_css_class else "session-{day}T{session.strftime('%H-%M')}",
                        )
                    )
                for product in sold_out_products_by_date_by_session[day][session]:
                    product_objects.append(
                        Div(
                            HTML(f"<p>Sold Out: {product.presentation.title}</p>"),
                            HTML(f'<p style="text-align: center; margin-bottom: 0em; font-size: smaller"><i>{", ".join([str(s) for s in product.presentation.speakers()])}</i></p>'),
                            css_class=f"session-{day}T{session.strftime('%H-%M')} {category.product_css_class} sold-out" if category.product_css_class else "session-{day}T{session.strftime('%H-%M')} sold-out",
                        )
                    )
                if (day, session) in disabled_sessions:
                    session_objects.append(
                        Div(
                            HTML(f"<h3>{session.strftime('%I:%M %p')}</h3>"),
                            HTML("<p><b>You have already paid for an event at this time, to change your selection you must cancel that event by contacting <a href=\"mailto:pycon-reg@python.org\">pycon-reg@python.org</a>.</b></p>"),
                            Div(
                                *product_objects,
                                css_class=f"session session-{day}T{session.strftime('%H-%M')}"
                            )
                        )
                    )
                elif (day, session) in pending_sessions:
                    session_objects.append(
                        Div(
                            HTML(f"<h3>{session.strftime('%I:%M %p')}</h3>"),
                            HTML("<p><b>You have already selected an event at this time, to change your selection you must remove the currently selected event first.</b></p>"),
                            Div(
                                *product_objects,
                                css_class=f"session session-{day}T{session.strftime('%H-%M')}"
                            )
                        )
                    )
                else:
                    session_objects.append(
                        Div(
                            HTML(f"<h3>{session.strftime('%I:%M %p')}</h3>"),
                            Div(
                                *product_objects,
                                css_class=f"session session-{day}T{session.strftime('%H-%M')}"
                            )
                        )
                    )
            layout_objects.append(
                Div(
                    HTML(f"<h2>{day.strftime('%A %B %d')}</h2>"),
                    *session_objects
                )
            )

        cls.helper.layout = Layout(
            Div(
                *layout_objects,
                css_class=category.form_css_class if category.form_css_class else "",
            )
        )

    @classmethod
    def initial_data(cls, product_quantities):
        initial = {}
        for product, quantity, _, _ in product_quantities:
            initial[cls.field_name(product)] = bool(quantity)

        return initial

    def clean(self):
        cleaned_data = super(_PresentationProductsForm, self).clean()

        session_slots = set()
        for name, value in cleaned_data.copy().items():
            if name.startswith(self.PRODUCT_PREFIX) and int(value) == 1:
                product_id = int(name[len(self.PRODUCT_PREFIX):])
                slot = inventory.Product.objects.get(pk=product_id).presentation.slot.start_datetime
                if slot in session_slots:
                    self.add_error(name, 'Only one session may be selected per slot')
                session_slots.add(slot)

        return cleaned_data

    def product_quantities(self):
        for name, value in self.cleaned_data.items():
            if name.startswith(self.PRODUCT_PREFIX):
                product_id = int(name[len(self.PRODUCT_PREFIX):])
                yield (product_id, int(value), None, None)

class _VoucherForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(_VoucherForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Div(
                Fieldset('', 'voucher'),
                css_class="registration-fieldset",
            )
        )

    @property
    def contains_errors(self):
        return True if self.errors else False

    required_css_class = 'label-required'

    voucher = forms.CharField(
        label="Voucher code",
        help_text="If you have a voucher code, enter it here",
        required=False,
    )

VoucherForm = get_form_class_from_settings('REGISTRASION_VOUCHER_FORM', _VoucherForm)

def staff_products_form_factory(user):
    ''' Creates a StaffProductsForm that restricts the available products to
    those that are available to a user. '''

    products = inventory.Product.objects.all()
    products = ProductController.available_products(user, products=products)

    product_ids = [product.id for product in products]
    product_set = inventory.Product.objects.filter(id__in=product_ids)

    class StaffProductsForm(forms.Form):
        ''' Form for allowing staff to add an item to a user's cart. '''

        product = forms.ModelChoiceField(
            widget=forms.Select,
            queryset=product_set,
        )

        quantity = forms.IntegerField(
            min_value=0,
        )

        price_override = forms.DecimalField(
            min_value=0,
            required=False,
        )

    return StaffProductsForm


def staff_products_formset_factory(user):
    ''' Creates a formset of StaffProductsForm for the given user. '''
    form_type = staff_products_form_factory(user)
    return forms.formset_factory(form_type)


def substitute_products_form_factory(user):

    products = inventory.Product.objects.all()
    product_ids = [product.id for product in products]
    product_set = inventory.Product.objects.filter(id__in=product_ids)

    class SubstituteProductsForm(forms.Form):
        line_item_id = forms.CharField(disabled=True)
        quantity = forms.IntegerField(required=False)
        product = forms.ModelChoiceField(
            widget=forms.Select,
            queryset=product_set,
            required=False,
        )
        price = forms.DecimalField(disabled=True)

    return SubstituteProductsForm

def substitute_products_formset_factory(user):
    form_type = substitute_products_form_factory(user)
    return forms.formset_factory(form_type, extra=0)


class InvoicesWithProductAndStatusForm(forms.Form):

    required_css_class = 'label-required'

    invoice = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        queryset=commerce.Invoice.objects.all(),
    )

    def __init__(self, *a, **k):
        category = k.pop('category', None) or []
        product = k.pop('product', None) or []
        status = int(k.pop('status', None) or 0)

        category = [int(i) for i in category]
        product = [int(i) for i in product]

        super(InvoicesWithProductAndStatusForm, self).__init__(*a, **k)
        self.helper = FormHelper()
        self.helper.form_method = "POST"
        self.helper.add_input(Submit('submit', 'Submit', css_class="btn-primary"))

        qs = commerce.Invoice.objects.filter(
            status=status or commerce.Invoice.STATUS_UNPAID,
        ).filter(
            Q(lineitem__product__category__in=category) |
            Q(lineitem__product__in=product)
        )

        # Uniqify
        qs = commerce.Invoice.objects.filter(
            id__in=qs,
        )

        qs = qs.select_related("user__attendee__attendeeprofilebase")
        qs = qs.order_by("id")

        self.fields['invoice'].queryset = qs
        # self.fields['invoice'].initial = [i.id for i in qs] # UNDO THIS LATER


class InvoiceEmailForm(InvoicesWithProductAndStatusForm):

    ACTION_PREVIEW = 1
    ACTION_SEND = 2

    ACTION_CHOICES = (
        (ACTION_PREVIEW, "Preview"),
        (ACTION_SEND, "Send emails"),
    )

    from_email = forms.CharField()
    subject = forms.CharField()
    body = forms.CharField(
        widget=forms.Textarea,
    )
    action = forms.TypedChoiceField(
        widget=forms.RadioSelect,
        coerce=int,
        choices=ACTION_CHOICES,
        initial=ACTION_PREVIEW,
    )

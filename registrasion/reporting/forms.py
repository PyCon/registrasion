from registrasion.models import conditions
from registrasion.models import inventory

from symposion.proposals import models as proposals_models

from crispy_forms.helper import FormHelper

from django import forms

# Reporting forms.


def mix_form(*a):
    ''' Creates a new form class out of all the supplied forms '''

    bases = tuple(a)
    return type("MixForm", bases, {})


class DiscountForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(DiscountForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False

    required_css_class = 'label-required'

    discount = forms.ModelMultipleChoiceField(
        queryset=conditions.DiscountBase.objects.all(),
        required=False,
    )


class ProductAndCategoryForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(ProductAndCategoryForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False

    required_css_class = 'label-required'

    product = forms.ModelMultipleChoiceField(
        queryset=inventory.Product.objects.select_related("category"),
        required=False,
    )
    category = forms.ModelMultipleChoiceField(
        queryset=inventory.Category.objects.all(),
        required=False,
    )


class UserIdForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(UserIdForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False

    required_css_class = 'label-required'

    user = forms.IntegerField(
        label="User ID",
        required=False,
    )


class ProposalKindForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(ProposalKindForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False

    required_css_class = 'label-required'

    kind = forms.ModelMultipleChoiceField(
        queryset=proposals_models.ProposalKind.objects.all(),
        required=False,
    )


class GroupByForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(GroupByForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False

    required_css_class = 'label-required'

    GROUP_BY_CATEGORY = "category"
    GROUP_BY_PRODUCT = "product"

    choices = (
        (GROUP_BY_CATEGORY, "Category"),
        (GROUP_BY_PRODUCT, "Product"),
    )

    group_by = forms.ChoiceField(
        label="Group by",
        choices=choices,
        required=False,
    )


def model_fields_form_factory(model):
    ''' Creates a form for specifying fields from a model to display. '''

    fields = model._meta.get_fields()

    choices = []
    for field in fields:
        if hasattr(field, "verbose_name"):
            choices.append((field.name, field.verbose_name))

    class ModelFieldsForm(forms.Form):
        def __init__(self, *args, **kwargs):
            super(ModelFieldsForm, self).__init__(*args, **kwargs)
            self.helper = FormHelper()
            self.helper.form_tag = False

        fields = forms.MultipleChoiceField(
            choices=choices,
            required=False,
        )

    return ModelFieldsForm
